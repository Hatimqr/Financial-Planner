.PHONY: run

run:
	bash -c 'eval "$$(conda shell.bash hook 2>/dev/null)" && conda activate fin_man && python -m ledger run'
