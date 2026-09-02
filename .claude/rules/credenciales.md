### Credenciales

**Por ningún motivo una credencial puede llegar al repositorio.** No hay excepción por
repositorio privado, por archivo de documentación, ni por "es solo un ejemplo": el historial de
git es permanente, sobrevive a cualquier cambio de visibilidad y viaja en cada clon. Una
credencial empujada se considera comprometida y hay que rotarla, no borrarla.

Cuenta como credencial cualquier usuario, contraseña, token, JWT, cadena de conexión o llave
que abra un sistema real, **aunque sea trivial, por defecto, o idéntica al nombre de usuario**.
Que una contraseña sea adivinable no la vuelve publicable: la vuelve urgente de rotar.

- Los valores reales viven **solo** en `.env`, que está en `.gitignore`.
- `.env.example` lleva marcadores de posición, nunca valores que funcionen.
- Al describir un problema de seguridad, se nombra **qué** credencial es y **dónde** vive, sin
  reproducir su valor: «las de Airflow son administrativas y usuario y contraseña coinciden»
  dice lo mismo sin filtrar nada.
- Las URL e IP internas no son credenciales, pero se tratan con el mismo cuidado si el
  repositorio deja de ser privado.

**Atención especial en `docs/session-context/contexto-sesion-*.md`.** Son el punto donde esto ya
falló una vez: al narrar una sesión es natural escribir el comando o el valor exacto que se usó,
y ahí se cuela. Antes de commitear cualquiera de esos archivos, releerlo buscando valores
concretos y sustituirlos por su descripción. El hook de `gitleaks` es la última red, no la
primera: no todo formato de credencial lo dispara.
