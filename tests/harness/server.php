<?php
/**
 * Serveur de test SANS Docker ni MongoDB :
 *   php -S 127.0.0.1:8099 tests/harness/server.php
 * Expose /soap/clients (WSDL + SOAP) avec un dépôt en mémoire.
 * Contrôle de panne : POST /_test/down et /_test/up (simule MongoDB indisponible).
 */
$root = dirname(__DIR__, 2) . '/laravel-app/app';
foreach (['Repositories/RepositoryUnavailableException', 'Repositories/ClientRepositoryInterface', 'Soap/ClientFault',
          'Soap/ClientValidator', 'Soap/ClientSoapService', 'Soap/SoapEndpoint'] as $f) {
    require_once "$root/$f.php";
}
require_once __DIR__ . '/InMemoryClientRepository.php';

$stateFile = sys_get_temp_dir() . '/soap_harness_state.ser';
$repo = is_file($stateFile) ? unserialize(file_get_contents($stateFile)) : new InMemoryClientRepository();
$save = fn () => file_put_contents($stateFile, serialize($repo));

$path = parse_url($_SERVER['REQUEST_URI'], PHP_URL_PATH);
$endpointUrl = 'http://' . $_SERVER['HTTP_HOST'] . '/soap/clients';
$endpoint = new App\Soap\SoapEndpoint(
    new App\Soap\ClientSoapService($repo),
    dirname(__DIR__, 2) . '/laravel-app/resources/wsdl/clients.wsdl',
    sys_get_temp_dir() . '/soap_harness_wsdl'
);

header('Content-Type: text/xml; charset=utf-8');
if ($path === '/soap/clients' && $_SERVER['REQUEST_METHOD'] === 'GET') {
    echo $endpoint->wsdl($endpointUrl);
} elseif ($path === '/soap/clients' && $_SERVER['REQUEST_METHOD'] === 'POST') {
    [$status, $body] = $endpoint->handle(file_get_contents('php://input'), $endpointUrl);
    http_response_code($status);
    echo $body;
    $save();
} elseif ($path === '/_test/down' || $path === '/_test/up') {
    $repo->down = $path === '/_test/down';
    $save();
    echo '<ok/>';
} elseif ($path === '/_test/reset') {
    @unlink($stateFile);
    echo '<ok/>';
} else {
    http_response_code(404);
    echo '<not-found/>';
}
