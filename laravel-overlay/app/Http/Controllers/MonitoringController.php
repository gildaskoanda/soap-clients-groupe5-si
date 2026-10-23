<?php

namespace App\Http\Controllers;

use App\Repositories\ClientRepositoryInterface;
use App\Repositories\RepositoryUnavailableException;
use Illuminate\Http\JsonResponse;

/** Endpoints consommés par Zabbix (HTTP agent). */
class MonitoringController extends Controller
{
    public function __construct(private ClientRepositoryInterface $repo)
    {
    }

    /** 200 si MongoDB répond, 503 sinon. */
    public function health(): JsonResponse
    {
        try {
            $this->repo->ping();
            return response()->json(['status' => 'ok', 'mongodb' => 'up']);
        } catch (RepositoryUnavailableException) {
            return response()->json(['status' => 'degraded', 'mongodb' => 'down'], 503);
        }
    }

    /** Indicateurs agrégés sur les 5 dernières minutes. */
    public function stats(): JsonResponse
    {
        try {
            return response()->json($this->repo->stats(300));
        } catch (RepositoryUnavailableException) {
            return response()->json(['error' => 'mongodb_unavailable'], 503);
        }
    }
}
