<?php

return [
    'uri'      => env('MONGO_URI', 'mongodb://app:app_password@mongo:27017/clients_db?authSource=clients_db'),
    'database' => env('MONGO_DB', 'clients_db'),
];
