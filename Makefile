.PHONY: install run test

install:
	python -m pip install -e ".[test]"

run:
	uvicorn app.main:app --reload

test:
	pytest
