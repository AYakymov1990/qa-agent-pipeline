# Читання окремих змінних з .env без виконання файла (паролі в оточення не потрапляють).
envget() {
  local key="$1"
  [ -f .env ] || return 0
  grep -E "^${key}=" .env | tail -1 | cut -d= -f2- | sed -e 's/^"//' -e 's/"$//'
}
