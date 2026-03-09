#!/usr/bin/env bash
set -Eeuo pipefail

REPO_DIR="$HOME/cm_bot"
BRANCH="main"

msg() {
  printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"
}

die() {
  msg "ERROR: $*"
  exit 1
}

cd "$REPO_DIR" || die "No existe la carpeta $REPO_DIR"

git rev-parse --is-inside-work-tree >/dev/null 2>&1 || die "Esta carpeta no es un repositorio git"

if ! git diff --quiet || ! git diff --cached --quiet; then
  :
elif [[ -z "$(git ls-files --others --exclude-standard)" ]]; then
  msg "No hay cambios para subir."
  exit 0
fi

COMMIT_MSG="${1:-Actualización automática $(date '+%Y-%m-%d %H:%M:%S')}"

msg "Verificando rama actual..."
CURRENT_BRANCH="$(git branch --show-current)"
if [[ -z "$CURRENT_BRANCH" ]]; then
  die "No se pudo detectar la rama actual"
fi

if [[ "$CURRENT_BRANCH" != "$BRANCH" ]]; then
  msg "Cambiando a rama $BRANCH..."
  git checkout "$BRANCH" || die "No se pudo cambiar a la rama $BRANCH"
fi

msg "Agregando archivos..."
git add .

msg "Creando commit..."
if git diff --cached --quiet; then
  msg "No hay cambios preparados para commit."
  exit 0
fi

git commit -m "$COMMIT_MSG"

msg "Enviando a GitHub..."
git push origin "$BRANCH"

msg "Repositorio actualizado correctamente."
