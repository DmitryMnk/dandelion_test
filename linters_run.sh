chmod +x linters_run.sh
directory="${1:-.}"

venvPath="./venv/bin/activate"

source "$venvPath"

echo "Start black..."
black "$directory"

echo "Start isort..."
isort "$directory"

echo "Start mypy..."
mypy "$directory"

echo "Start ruff..."
ruff check "$directory"

echo "Done."
