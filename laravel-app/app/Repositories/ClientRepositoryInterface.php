<?php

namespace App\Repositories;

/**
 * Accès à la base de référence des clients (MongoDB).
 *
 * Les clients sont échangés sous forme de tableaux dont les clés suivent le WSDL
 * (codeClient, nom, prenom, email, telephone, ville, pays, statut, dateInscription,
 * version, synchronisation).
 */
interface ClientRepositoryInterface
{
    /** @return array<string,mixed>|null */
    public function find(string $codeClient): ?array;

    /**
     * @param array{nom?:string,ville?:string,statut?:string} $criteria
     * @return array{total:int,items:list<array<string,mixed>>}
     */
    public function search(array $criteria, int $page, int $pageSize): array;

    public function emailTaken(string $email, string $exceptCodeClient): bool;

    /**
     * Mise à jour atomique conditionnée par la version courante (verrou optimiste).
     *
     * @param array<string,string> $changes champs métier modifiés (clés WSDL)
     * @return array<string,mixed>|null null si la version a changé entre-temps
     */
    public function update(string $codeClient, int $currentVersion, array $changes): ?array;

    /** Trace un appel SOAP pour la supervision (ne doit jamais lever d'exception). */
    public function recordCall(string $operation, bool $ok, ?string $faultCode, int $durationMs): void;

    /** Lève RepositoryUnavailableException si la base ne répond pas. */
    public function ping(): void;

    /**
     * Indicateurs de supervision sur une fenêtre glissante.
     *
     * @return array<string,mixed>
     */
    public function stats(int $windowSeconds): array;
}
