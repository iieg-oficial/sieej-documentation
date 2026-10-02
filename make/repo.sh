env_word() {
    if [ "$1" = 'prod' ]; then printf 'produccion'; else printf 'desarrollo'; fi
}

env_guard() {
    if [ ! -f .env.production ] && [ -f .env ]; then
        fail 'Env:.env ahora se llama .env.production' \
             'Renombralo una vez y agrega WEB_BIND_ADDR: mv .env .env.production'
    fi
    if [ ! -f .env.production ]; then
        fail 'Env:falta .env.production' \
             'Crealo desde la plantilla y llenalo: cp .env.production.example .env.production'
    fi
    row 'Env' '.env.production' "$C_GREEN"
}
