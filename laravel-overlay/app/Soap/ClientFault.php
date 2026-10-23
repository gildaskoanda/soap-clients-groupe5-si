<?php

namespace App\Soap;

/**
 * Erreur SOAP (Fault) typée du service clients.
 *
 * Le détail est sérialisé selon l'élément XSD <ClientFault> déclaré dans le WSDL :
 *   <detail><ClientFault><code/><message/><champ/></ClientFault></detail>
 */
class ClientFault extends \SoapFault
{
    public const VALIDATION_ERROR     = 'VALIDATION_ERROR';
    public const CLIENT_NOT_FOUND     = 'CLIENT_NOT_FOUND';
    public const EMAIL_ALREADY_USED   = 'EMAIL_ALREADY_USED';
    public const VERSION_CONFLICT     = 'VERSION_CONFLICT';
    public const SERVICE_UNAVAILABLE  = 'SERVICE_UNAVAILABLE';
    public const INTERNAL_ERROR       = 'INTERNAL_ERROR';

    public function __construct(
        public readonly string $errorCode,
        string $message,
        ?string $field = null,
        string $faultCode = 'Client'
    ) {
        $detail = new \stdClass();
        $detail->code = $errorCode;
        $detail->message = $message;
        if ($field !== null) {
            $detail->champ = $field;
        }
        parent::__construct($faultCode, $message, null, $detail, 'ClientFault');
    }

    public static function validation(string $message, string $field): self
    {
        return new self(self::VALIDATION_ERROR, $message, $field);
    }

    public static function notFound(string $codeClient): self
    {
        return new self(self::CLIENT_NOT_FOUND, "Aucun client avec le code $codeClient.", 'codeClient');
    }

    public static function server(string $errorCode, string $message): self
    {
        return new self($errorCode, $message, null, 'Server');
    }

    public function isServerSide(): bool
    {
        return in_array($this->errorCode, [self::SERVICE_UNAVAILABLE, self::INTERNAL_ERROR], true);
    }
}
