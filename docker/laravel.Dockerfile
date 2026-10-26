# Service SOAP : Laravel 12 + ext-soap + ext-mongodb.
# Versions épinglées ensemble : ext-mongodb 1.21.x <-> mongodb/mongodb ^1.21 (la lib 1.x est incompatible avec l'ext 2.x installée par défaut par pecl).
# Laravel 11 est refusé par Composer (avis de sécurité, fin de support mars 2026).
# Laravel est installé proprement à la construction de l'image ; seul le code du projet
# (laravel-overlay/) est versionné dans le dépôt.
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
RUN composer create-project laravel/laravel:^12.0 . --prefer-dist --no-interaction \
 && composer require mongodb/mongodb:^1.21 --no-interaction --no-progress

# Code du projet : écrase/complète le squelette Laravel
COPY laravel-overlay/ /var/www/html/

RUN mkdir -p storage/app/wsdl \
 && chown -R www-data:www-data storage bootstrap/cache \
 && composer dump-autoload --optimize --no-interaction

EXPOSE 80
