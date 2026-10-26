# Service SOAP : Laravel 12 + ext-soap + ext-mongodb.
# Le projet Laravel COMPLET est versionné dans laravel-app/ (composer.json + composer.lock) :
# `composer install` installe exactement les versions du lockfile, sans résolution de versions.
# Versions épinglées ensemble : ext-mongodb 1.21.x <-> mongodb/mongodb ^1.21
# (la bibliothèque 1.x est incompatible avec l'extension 2.x installée par défaut par pecl).
FROM php:8.3-apache

RUN apt-get update \
 && apt-get install -y --no-install-recommends git unzip libxml2-dev libssl-dev libzip-dev pkg-config \
 && docker-php-ext-install soap zip \
 && pecl install mongodb-1.21.10 \
 && docker-php-ext-enable mongodb \
 && a2enmod rewrite \
 && rm -rf /var/lib/apt/lists/*

COPY --from=composer:2 /usr/bin/composer /usr/bin/composer

ENV APACHE_DOCUMENT_ROOT=/var/www/html/public
RUN sed -ri -e 's!/var/www/html!${APACHE_DOCUMENT_ROOT}!g' /etc/apache2/sites-available/*.conf /etc/apache2/apache2.conf /etc/apache2/conf-available/*.conf

WORKDIR /var/www/html
ENV COMPOSER_ALLOW_SUPERUSER=1

# 1) Dépendances figées par composer.lock (couche mise en cache tant que le lockfile ne change pas)
COPY laravel-app/composer.json laravel-app/composer.lock ./
RUN composer install --no-interaction --prefer-dist --no-progress --no-scripts --no-autoloader --no-audit

# 2) Code du projet, puis autoload et découverte des paquets
COPY laravel-app/ ./
RUN cp -n .env.example .env \
 && mkdir -p storage/app/wsdl \
 && composer dump-autoload --optimize --no-interaction \
 && php artisan key:generate --force \
 && chown -R www-data:www-data storage bootstrap/cache

EXPOSE 80
