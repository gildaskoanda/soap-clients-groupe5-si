<?php

namespace App\Providers;

use App\Repositories\ClientRepositoryInterface;
use App\Repositories\MongoClientRepository;
use App\Soap\ClientSoapService;
use App\Soap\SoapEndpoint;
use Illuminate\Support\ServiceProvider;

class AppServiceProvider extends ServiceProvider
{
    public function register(): void
    {
        $this->app->singleton(ClientRepositoryInterface::class, fn () => new MongoClientRepository(
            config('mongo.uri'),
            config('mongo.database')
        ));

        $this->app->singleton(SoapEndpoint::class, fn ($app) => new SoapEndpoint(
            new ClientSoapService($app->make(ClientRepositoryInterface::class)),
            resource_path('wsdl/clients.wsdl'),
            storage_path('app/wsdl')
        ));
    }

    public function boot(): void
    {
        //
    }
}
