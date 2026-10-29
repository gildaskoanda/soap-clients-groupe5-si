<?php

namespace App\Soap;

/**
 * Point d'entrée SOAP indépendant du framework : publie le WSDL et traite les enveloppes.
 * Utilisé par le contrôleur Laravel et par le serveur de test sans Docker.
 */
class SoapEndpoint
{
    public function __construct(
        private ClientSoapService $service,
        private string $wsdlTemplatePath,
        private string $runtimeDir
    ) {
    }

    /** WSDL publié, avec l'adresse réelle du service. */
    public function wsdl(string $endpointUrl): string
    {
        return str_replace('__ENDPOINT__', htmlspecialchars($endpointUrl, ENT_XML1 | ENT_QUOTES), file_get_contents($this->wsdlTemplatePath));
    }

    /** @return array{0:int,1:string} statut HTTP et corps XML */
    public function handle(string $envelope, string $endpointUrl): array
    {
        if (trim($envelope) === '') {
            return [500, $this->plainFault('Client', 'Enveloppe SOAP vide.')];
        }

        $wsdlFile = $this->materializeWsdl($endpointUrl);
        ini_set('soap.wsdl_cache_enabled', '0');

        try {
            $server = new \SoapServer($wsdlFile, ['soap_version' => SOAP_1_1, 'cache_wsdl' => WSDL_CACHE_NONE]);
            $server->setObject($this->service);
            ob_start();
            $server->handle($envelope);
            $body = (string) ob_get_clean();
        } catch (\Throwable $e) {
            if (ob_get_level() > 0) {
                ob_end_clean();
            }
            return [500, $this->plainFault('Server', 'Erreur interne du service.')];
        }

        // SOAP 1.1 impose le statut HTTP 500 pour une réponse contenant un Fault.
        $status = str_contains($body, ':Fault>') ? 500 : 200;
        return [$status, $body];
    }

    private function materializeWsdl(string $endpointUrl): string
    {
        if (!is_dir($this->runtimeDir)) {
            @mkdir($this->runtimeDir, 0775, true);
        }
        $file = rtrim($this->runtimeDir, '/') . '/clients.wsdl';
        $content = $this->wsdl($endpointUrl);
        if (!is_file($file) || md5_file($file) !== md5($content)) {
            file_put_contents($file, $content, LOCK_EX);
        }
        return $file;
    }

    private function plainFault(string $code, string $message): string
    {
        return '<?xml version="1.0" encoding="UTF-8"?>'
            . '<SOAP-ENV:Envelope xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/"><SOAP-ENV:Body><SOAP-ENV:Fault>'
            . '<faultcode>SOAP-ENV:' . $code . '</faultcode><faultstring>' . htmlspecialchars($message, ENT_XML1) . '</faultstring>'
            . '</SOAP-ENV:Fault></SOAP-ENV:Body></SOAP-ENV:Envelope>';
    }
}
