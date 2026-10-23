<?php

namespace App\Soap;

use App\Repositories\ClientRepositoryInterface;
use App\Repositories\RepositoryUnavailableException;

/**
 * Opérations SOAP exposées : getClientDetails, searchClients, updateClient.
 * MongoDB est la base de référence : le service ne lit ni n'écrit jamais MySQL.
 */
class ClientSoapService
{
    private ClientValidator $validator;

    public function __construct(private ClientRepositoryInterface $repo, ?ClientValidator $validator = null)
    {
        $this->validator = $validator ?? new ClientValidator();
    }

    public function getClientDetails(object $params): array
    {
        return $this->run('getClientDetails', function () use ($params) {
            $code = $this->validator->code($params->codeClient ?? null);
            $client = $this->repo->find($code) ?? throw ClientFault::notFound($code);
            return ['client' => $client];
        });
    }

    public function searchClients(object $params): array
    {
        return $this->run('searchClients', function () use ($params) {
            $criteria = $this->validator->searchCriteria($params);
            [$page, $size] = $this->validator->paging($params);
            $result = $this->repo->search($criteria, $page, $size);
            return [
                'total'      => $result['total'],
                'page'       => $page,
                'taillePage' => $size,
                'clients'    => $result['items'],
            ];
        });
    }

    public function updateClient(object $params): array
    {
        return $this->run('updateClient', function () use ($params) {
            $code     = $this->validator->code($params->codeClient ?? null);
            $changes  = $this->validator->updateChanges($params);
            $expected = $this->validator->expectedVersion($params);

            $current = $this->repo->find($code) ?? throw ClientFault::notFound($code);

            if ($expected !== null && $expected !== $current['version']) {
                throw new ClientFault(
                    ClientFault::VERSION_CONFLICT,
                    "Conflit de version : attendue $expected, courante {$current['version']}.",
                    'versionAttendue'
                );
            }
            if (isset($changes['email']) && $this->repo->emailTaken($changes['email'], $code)) {
                throw new ClientFault(ClientFault::EMAIL_ALREADY_USED, 'Cette adresse e-mail est déjà utilisée.', 'email');
            }

            $updated = $this->repo->update($code, $current['version'], $changes);
            if ($updated === null) {
                // Une autre écriture a incrémenté la version entre la lecture et l'écriture.
                throw new ClientFault(
                    ClientFault::VERSION_CONFLICT,
                    'Le client a été modifié par une autre requête, relire puis réessayer.',
                    'versionAttendue'
                );
            }
            return [
                'message' => 'Client mis à jour dans MongoDB (en attente de réconciliation vers MySQL).',
                'client'  => $updated,
            ];
        });
    }

    /** Exécute une opération en traduisant les erreurs techniques en Faults et en traçant l'appel. */
    private function run(string $operation, callable $fn): array
    {
        $start = hrtime(true);
        $fault = null;
        try {
            return $fn();
        } catch (ClientFault $e) {
            $fault = $e;
        } catch (RepositoryUnavailableException $e) {
            $fault = ClientFault::server(ClientFault::SERVICE_UNAVAILABLE, 'Base de données indisponible, réessayer plus tard.');
        } catch (\Throwable $e) {
            error_log('[soap-clients] ' . $e::class . ': ' . $e->getMessage());
            $fault = ClientFault::server(ClientFault::INTERNAL_ERROR, 'Erreur interne du service.');
        } finally {
            $ms = (int) ((hrtime(true) - $start) / 1_000_000);
            try {
                $this->repo->recordCall($operation, $fault === null, $fault?->errorCode, $ms);
            } catch (\Throwable) {
                // La supervision ne doit jamais casser une requête métier.
            }
        }
        throw $fault;
    }
}
