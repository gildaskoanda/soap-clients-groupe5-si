<?php

namespace App\Repositories;

/** La base de référence (MongoDB) est injoignable ou a expiré. */
class RepositoryUnavailableException extends \RuntimeException
{
}
