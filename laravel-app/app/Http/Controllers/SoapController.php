<?php

namespace App\Http\Controllers;

use App\Soap\SoapEndpoint;
use Illuminate\Http\Request;
use Illuminate\Http\Response;

class SoapController extends Controller
{
    public function __construct(private SoapEndpoint $endpoint)
    {
    }

    private function endpointUrl(Request $request): string
    {
        return config('soap.public_url') ?: $request->getSchemeAndHttpHost() . '/soap/clients';
    }

    /** GET /soap/clients?wsdl  ->  contrat WSDL */
    public function wsdl(Request $request): Response
    {
        return response($this->endpoint->wsdl($this->endpointUrl($request)), 200, [
            'Content-Type' => 'text/xml; charset=utf-8',
        ]);
    }

    /** POST /soap/clients  ->  enveloppe SOAP 1.1 */
    public function handle(Request $request): Response
    {
        [$status, $body] = $this->endpoint->handle($request->getContent(), $this->endpointUrl($request));
        return response($body, $status, ['Content-Type' => 'text/xml; charset=utf-8']);
    }
}
