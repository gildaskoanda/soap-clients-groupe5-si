<?php

namespace App\Repositories;

use MongoDB\BSON\Regex;
use MongoDB\BSON\UTCDateTime;
use MongoDB\Client;
use MongoDB\Collection;
use MongoDB\Driver\Exception\Exception as MongoDriverException;
use MongoDB\Model\BSONDocument;
use MongoDB\Operation\FindOneAndUpdate;

/** Implémentation MongoDB (base de référence). Collections : clients, soap_calls, etl_runs. */
class MongoClientRepository implements ClientRepositoryInterface
{
    private ?Client $client = null;

    public function __construct(private string $uri, private string $database)
    {
    }

    private function client(): Client
    {
        return $this->client ??= new Client($this->uri, [
            'serverSelectionTimeoutMS' => 2000,
            'connectTimeoutMS'         => 2000,
            'socketTimeoutMS'          => 5000,
        ]);
    }

    private function col(string $name): Collection
    {
        return $this->client()->selectCollection($this->database, $name);
    }

    /** Exécute une opération Mongo en traduisant les erreurs de driver. */
    private function guard(callable $fn): mixed
    {
        try {
            return $fn();
        } catch (MongoDriverException $e) {
            throw new RepositoryUnavailableException($e->getMessage(), 0, $e);
        }
    }

    public function find(string $codeClient): ?array
    {
        $doc = $this->guard(fn () => $this->col('clients')->findOne(['code_client' => $codeClient]));
        return $doc === null ? null : $this->toClient($doc);
    }

    public function search(array $criteria, int $page, int $pageSize): array
    {
        $filter = [];
        if (isset($criteria['nom'])) {
            $filter['nom'] = new Regex(preg_quote($criteria['nom'], '/'), 'i');
        }
        if (isset($criteria['ville'])) {
            $filter['ville'] = new Regex(preg_quote($criteria['ville'], '/'), 'i');
        }
        if (isset($criteria['statut'])) {
            $filter['statut'] = $criteria['statut'];
        }

        return $this->guard(function () use ($filter, $page, $pageSize) {
            $col = $this->col('clients');
            $total = $col->countDocuments($filter);
            $cursor = $col->find($filter, [
                'sort'  => ['nom' => 1, 'prenom' => 1, 'code_client' => 1],
                'skip'  => ($page - 1) * $pageSize,
                'limit' => $pageSize,
            ]);
            $items = [];
            foreach ($cursor as $doc) {
                $items[] = $this->toClient($doc);
            }
            return ['total' => $total, 'items' => $items];
        });
    }

    public function emailTaken(string $email, string $exceptCodeClient): bool
    {
        return (bool) $this->guard(fn () => $this->col('clients')->countDocuments([
            'email'       => $email,
            'code_client' => ['$ne' => $exceptCodeClient],
        ], ['limit' => 1]));
    }

    public function update(string $codeClient, int $currentVersion, array $changes): ?array
    {
        $set = [
            'updated_at'       => new UTCDateTime(),
            'locally_modified' => true,
            'sync_status'      => 'pending_mysql',
            'source'           => 'soap',
        ];
        foreach ($changes as $field => $value) {
            $set[$field] = $value;
        }

        $doc = $this->guard(fn () => $this->col('clients')->findOneAndUpdate(
            ['code_client' => $codeClient, 'version' => $currentVersion],
            ['$set' => $set, '$inc' => ['version' => 1]],
            ['returnDocument' => FindOneAndUpdate::RETURN_DOCUMENT_AFTER]
        ));
        return $doc === null ? null : $this->toClient($doc);
    }

    public function recordCall(string $operation, bool $ok, ?string $faultCode, int $durationMs): void
    {
        try {
            $this->col('soap_calls')->insertOne([
                'operation'   => $operation,
                'ok'          => $ok,
                'fault_code'  => $faultCode,
                'duration_ms' => $durationMs,
                'ts'          => new UTCDateTime(),
            ]);
        } catch (\Throwable) {
            // best effort
        }
    }

    public function ping(): void
    {
        $this->guard(fn () => $this->client()->selectDatabase($this->database)->command(['ping' => 1]));
    }

    public function stats(int $windowSeconds): array
    {
        return $this->guard(function () use ($windowSeconds) {
            $since = new UTCDateTime((time() - $windowSeconds) * 1000);
            $agg = $this->col('soap_calls')->aggregate([
                ['$match' => ['ts' => ['$gte' => $since]]],
                ['$group' => [
                    '_id'           => null,
                    'calls'         => ['$sum' => 1],
                    'faults'        => ['$sum' => ['$cond' => ['$ok', 0, 1]]],
                    'server_faults' => ['$sum' => ['$cond' => [['$in' => ['$fault_code', ['SERVICE_UNAVAILABLE', 'INTERNAL_ERROR']]], 1, 0]]],
                    'avg_ms'        => ['$avg' => '$duration_ms'],
                    'max_ms'        => ['$max' => '$duration_ms'],
                ]],
            ])->toArray();
            $row = $agg[0] ?? null;

            $lastRun = $this->col('etl_runs')->findOne([], ['sort' => ['finished_at' => -1]]);
            $etlAge = null;
            if ($lastRun !== null && isset($lastRun['finished_at'])) {
                $etlAge = max(0, time() - (int) ($lastRun['finished_at']->toDateTime()->getTimestamp()));
            }

            return [
                'window_seconds'          => $windowSeconds,
                'calls'                   => (int) ($row['calls'] ?? 0),
                'faults'                  => (int) ($row['faults'] ?? 0),
                'server_faults'           => (int) ($row['server_faults'] ?? 0),
                'avg_ms'                  => round((float) ($row['avg_ms'] ?? 0), 1),
                'max_ms'                  => (int) ($row['max_ms'] ?? 0),
                'clients_total'           => $this->col('clients')->countDocuments([]),
                'pending_reconciliation'  => $this->col('clients')->countDocuments(['locally_modified' => true]),
                'etl_last_status'         => $lastRun['status'] ?? 'never_run',
                'etl_last_age_seconds'    => $etlAge,
                'etl_last_rejected'       => (int) ($lastRun['rejected'] ?? 0),
            ];
        });
    }

    /** Convertit un document Mongo en tableau au format du WSDL. */
    private function toClient(BSONDocument|array $doc): array
    {
        $d = $doc instanceof BSONDocument ? $doc->getArrayCopy() : $doc;
        $out = [
            'codeClient'      => (string) $d['code_client'],
            'nom'             => (string) ($d['nom'] ?? ''),
            'prenom'          => (string) ($d['prenom'] ?? ''),
            'email'           => (string) ($d['email'] ?? ''),
            'statut'          => (string) ($d['statut'] ?? 'actif'),
            'version'         => (int) ($d['version'] ?? 1),
            'synchronisation' => (string) ($d['sync_status'] ?? 'synced'),
        ];
        foreach (['telephone' => 'telephone', 'ville' => 'ville', 'pays' => 'pays', 'dateInscription' => 'date_inscription'] as $wsdl => $mongo) {
            if (isset($d[$mongo]) && $d[$mongo] !== '') {
                $out[$wsdl] = (string) $d[$mongo];
            }
        }
        return $out;
    }
}
