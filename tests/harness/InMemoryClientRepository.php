<?php

use App\Repositories\ClientRepositoryInterface;
use App\Repositories\RepositoryUnavailableException;

/** Dépôt en mémoire pour tester la couche SOAP sans MongoDB ni Laravel. */
class InMemoryClientRepository implements ClientRepositoryInterface
{
    /** @var array<string,array<string,mixed>> */
    public array $clients = [];
    public bool $down = false;
    public array $calls = [];

    public function __construct()
    {
        $villes = ['Bobo-Dioulasso', 'Ouagadougou', 'Koudougou', 'Banfora', 'Ouahigouya'];
        $noms = ['OUEDRAOGO', 'KONE', 'TRAORE', 'SAWADOGO', 'COULIBALY', 'SANOGO', 'DIALLO', 'BARRY'];
        $prenoms = ['Aminata', 'Moussa', 'Fatoumata', 'Ibrahim', 'Awa', 'Salif', 'Mariam', 'Issouf'];
        for ($i = 1; $i <= 40; $i++) {
            $code = sprintf('CLI-%06d', $i);
            $this->clients[$code] = [
                'codeClient' => $code, 'nom' => $noms[$i % 8], 'prenom' => $prenoms[($i * 3) % 8],
                'email' => "client$i@example.bf", 'telephone' => '+226 70 00 00 ' . sprintf('%02d', $i),
                'ville' => $villes[$i % 5], 'pays' => 'Burkina Faso',
                'statut' => ['actif', 'actif', 'inactif', 'suspendu'][$i % 4],
                'dateInscription' => '2025-01-' . sprintf('%02d', ($i % 28) + 1),
                'version' => 1, 'synchronisation' => 'synced',
            ];
        }
    }

    public function find(string $codeClient): ?array
    {
        $this->guard();
        return $this->clients[$codeClient] ?? null;
    }

    public function search(array $criteria, int $page, int $pageSize): array
    {
        $this->guard();
        $rows = array_values(array_filter($this->clients, function ($c) use ($criteria) {
            if (isset($criteria['nom']) && stripos($c['nom'], $criteria['nom']) === false) return false;
            if (isset($criteria['ville']) && stripos($c['ville'], $criteria['ville']) === false) return false;
            if (isset($criteria['statut']) && $c['statut'] !== $criteria['statut']) return false;
            return true;
        }));
        usort($rows, fn ($a, $b) => [$a['nom'], $a['prenom'], $a['codeClient']] <=> [$b['nom'], $b['prenom'], $b['codeClient']]);
        return ['total' => count($rows), 'items' => array_slice($rows, ($page - 1) * $pageSize, $pageSize)];
    }

    public function emailTaken(string $email, string $exceptCodeClient): bool
    {
        $this->guard();
        foreach ($this->clients as $c) {
            if ($c['email'] === $email && $c['codeClient'] !== $exceptCodeClient) return true;
        }
        return false;
    }

    public function update(string $codeClient, int $currentVersion, array $changes): ?array
    {
        $this->guard();
        $c = $this->clients[$codeClient] ?? null;
        if ($c === null || $c['version'] !== $currentVersion) return null;
        $c = array_merge($c, $changes, ['version' => $currentVersion + 1, 'synchronisation' => 'pending_mysql']);
        return $this->clients[$codeClient] = $c;
    }

    public function recordCall(string $operation, bool $ok, ?string $faultCode, int $durationMs): void
    {
        $this->calls[] = compact('operation', 'ok', 'faultCode', 'durationMs');
    }

    public function ping(): void
    {
        $this->guard();
    }

    public function stats(int $windowSeconds): array
    {
        return ['calls' => count($this->calls)];
    }

    private function guard(): void
    {
        if ($this->down) throw new RepositoryUnavailableException('down');
    }
}
