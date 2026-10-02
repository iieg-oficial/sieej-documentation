REPO_NAME    := sieej-documentation
COMPOSE_PROD := -f compose.yaml -f compose.prod.yaml
COMPOSE_DEV  := -f compose.yaml -f compose.dev.yaml
ENV_PROD     := .env.production
ENV_DEV      := .env.development

UP_PRE        := setup
DEPLOY_GUARDS  = env_guard

include make/common.mk

.PHONY: setup sync test mariachi-key

##@ Documentacion

setup: ## Crear el .env.development si falta
	@$(LIB)
	if [ ! -f $(ENV_DEV) ]; then
		cp .env.example $(ENV_DEV)
		row 'Env' 'creado' "$$C_GREEN" 'edita $(ENV_DEV)'
	fi

sync: ## Correr un ciclo del sincronizador ahora, sin esperar al siguiente
	@$(LIB)
	env=$$(resolve_env)
	if [ -z "$$env" ]; then nothing_running 'SYNC'; exit 0; fi
	banner 'SYNC' "$$(env_word "$$env")"
	rule
	run_step 'Sincronizar' dc "$$env" exec -T builder /usr/local/bin/entrypoint.sh una-vez
	rule
	printf '\n'

test: ## Correr los tests del datalayer en .venv
	@$(LIB)
	banner 'TEST' 'datalayer'
	rule
	if [ ! -x .venv/bin/python ]; then
		run_step 'Venv' sh -c 'python3 -m venv .venv && .venv/bin/pip install -q -e "datalayer[dev]"'
	fi
	run_step 'Pytest' .venv/bin/python -m pytest -q datalayer
	rule
	printf '\n'

mariachi-key: ## Generar la clave del sincronizador y mostrar la huella que va en mariachi
	@$(LIB)
	archivo=$(ENV_DEV)
	[ -f $(ENV_PROD) ] && archivo=$(ENV_PROD)
	[ -f "$$archivo" ] || { row 'Env' 'falta' "$$C_RED" "$$archivo"; exit 1; }
	banner 'MARIACHI' 'clave del sincronizador'
	if grep -q '^MARIACHI_SYNC_KEY=.\+' "$$archivo"; then
		confirm 'Ya hay una clave: reemplazarla corta la sincronización hasta poner su huella en mariachi.' 'reemplazar'
	fi
	clave=$$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')
	if grep -q '^MARIACHI_SYNC_KEY=' "$$archivo"; then
		sed -i "s|^MARIACHI_SYNC_KEY=.*|MARIACHI_SYNC_KEY=$$clave|" "$$archivo"
	else
		printf 'MARIACHI_SYNC_KEY=%s\n' "$$clave" >> "$$archivo"
	fi
	huella=$$(printf '%s' "$$clave" | sha256sum | cut -d' ' -f1)
	row 'Clave' 'guardada' "$$C_GREEN" "$$archivo"
	row 'Huella' "$$huella" "$$C_GREEN" 'SIEEJ_DOCUMENTACION_SYNC_SHA256 en mariachi'
	rule
	printf '\n'
