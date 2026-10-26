<?php

use App\Http\Controllers\MonitoringController;
use App\Http\Controllers\SoapController;
use Illuminate\Support\Facades\Route;

// Aucun groupe de middleware « web » : pas de session, pas de CSRF pour un service SOAP.
Route::get('/soap/clients', [SoapController::class, 'wsdl']);
Route::post('/soap/clients', [SoapController::class, 'handle']);

Route::get('/health', [MonitoringController::class, 'health']);
Route::get('/monitoring/stats', [MonitoringController::class, 'stats']);
