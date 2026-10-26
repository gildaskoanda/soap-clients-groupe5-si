<?php

namespace App\Soap;

/**
 * Règles de validation des paramètres SOAP. Toute violation lève un ClientFault
 * VALIDATION_ERROR indiquant le champ fautif.
 */
final class ClientValidator
{
    public const CODE_REGEX      = '/^CLI-\d{6}$/';
    public const NAME_REGEX      = '/^[\p{L}][\p{L} \'\-]{1,79}$/u';
    public const PHONE_REGEX     = '/^\+?[0-9][0-9 ]{7,17}$/';
    public const STATUTS         = ['actif', 'inactif', 'suspendu'];
    public const MAX_PAGE_SIZE   = 100;
    public const DEFAULT_PAGE_SIZE = 20;

    /** Champs modifiables par updateClient : clé WSDL => règle. */
    private const UPDATABLE = ['nom', 'prenom', 'email', 'telephone', 'ville', 'statut'];

    public function code(mixed $value, string $field = 'codeClient'): string
    {
        if (!is_string($value) || !preg_match(self::CODE_REGEX, trim($value))) {
            throw ClientFault::validation('Le code client doit respecter le format CLI-000000 (6 chiffres).', $field);
        }
        return trim($value);
    }

    /** @return array{nom?:string,ville?:string,statut?:string} */
    public function searchCriteria(object $p): array
    {
        $criteria = [];
        foreach (['nom', 'ville'] as $f) {
            if (isset($p->$f)) {
                $v = trim((string) $p->$f);
                if (mb_strlen($v) < 2 || mb_strlen($v) > 80) {
                    throw ClientFault::validation("Le critère « $f » doit contenir de 2 à 80 caractères.", $f);
                }
                $criteria[$f] = $v;
            }
        }
        if (isset($p->statut)) {
            $criteria['statut'] = $this->statut($p->statut);
        }
        return $criteria;
    }

    /** @return array{0:int,1:int} page, taillePage */
    public function paging(object $p): array
    {
        $page = isset($p->page) ? (int) $p->page : 1;
        $size = isset($p->taillePage) ? (int) $p->taillePage : self::DEFAULT_PAGE_SIZE;
        if ($page < 1) {
            throw ClientFault::validation('La page doit être supérieure ou égale à 1.', 'page');
        }
        if ($size < 1 || $size > self::MAX_PAGE_SIZE) {
            throw ClientFault::validation('taillePage doit être compris entre 1 et ' . self::MAX_PAGE_SIZE . '.', 'taillePage');
        }
        return [$page, $size];
    }

    /** @return array<string,string> uniquement les champs fournis, normalisés */
    public function updateChanges(object $p): array
    {
        $changes = [];
        foreach (self::UPDATABLE as $field) {
            if (!isset($p->$field)) {
                continue;
            }
            $value = trim((string) $p->$field);
            $changes[$field] = match ($field) {
                'nom', 'prenom' => $this->name($value, $field),
                'email'         => $this->email($value),
                'telephone'     => $this->phone($value),
                'ville'         => $this->city($value),
                'statut'        => $this->statut($value),
            };
        }
        if ($changes === []) {
            throw ClientFault::validation(
                'Aucun champ à modifier : fournir au moins nom, prenom, email, telephone, ville ou statut.',
                'updateClient'
            );
        }
        return $changes;
    }

    public function expectedVersion(object $p): ?int
    {
        if (!isset($p->versionAttendue)) {
            return null;
        }
        $v = (int) $p->versionAttendue;
        if ($v < 1) {
            throw ClientFault::validation('versionAttendue doit être un entier >= 1.', 'versionAttendue');
        }
        return $v;
    }

    private function name(string $v, string $field): string
    {
        if (!preg_match(self::NAME_REGEX, $v)) {
            throw ClientFault::validation("« $field » : 2 à 80 caractères, lettres, espaces, apostrophes et tirets uniquement.", $field);
        }
        return $field === 'nom'
            ? mb_strtoupper($v, 'UTF-8')
            : mb_convert_case($v, MB_CASE_TITLE, 'UTF-8');
    }

    private function email(string $v): string
    {
        if (mb_strlen($v) > 190 || filter_var($v, FILTER_VALIDATE_EMAIL) === false) {
            throw ClientFault::validation('Adresse e-mail invalide (190 caractères maximum).', 'email');
        }
        return mb_strtolower($v, 'UTF-8');
    }

    private function phone(string $v): string
    {
        if (!preg_match(self::PHONE_REGEX, $v)) {
            throw ClientFault::validation('Téléphone invalide : 8 à 18 chiffres/espaces, "+" initial autorisé.', 'telephone');
        }
        return $v;
    }

    private function city(string $v): string
    {
        if (mb_strlen($v) < 2 || mb_strlen($v) > 80) {
            throw ClientFault::validation('La ville doit contenir de 2 à 80 caractères.', 'ville');
        }
        return $v;
    }

    public function statut(mixed $v): string
    {
        $v = is_string($v) ? trim($v) : '';
        if (!in_array($v, self::STATUTS, true)) {
            throw ClientFault::validation('Statut invalide : actif, inactif ou suspendu.', 'statut');
        }
        return $v;
    }
}
