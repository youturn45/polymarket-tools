# Convenience tasks for running local utility scripts.

python := "uv run python"

@help:
	@just --list

@gamma:
	{{python}} src/utils/gamma_parse.py

@kelly price true_prob side bankroll="1000":
	{{python}} src/utils/kelly_calculator.py --price {{price}} --true-prob {{true_prob}} --side {{side}} --bankroll {{bankroll}}

@kelly-buy price true_prob bankroll="1000":
	{{python}} src/utils/kelly_calculator.py --price {{price}} --true-prob {{true_prob}} --side BUY --bankroll {{bankroll}}

@kelly-sell price true_prob bankroll="1000":
	{{python}} src/utils/kelly_calculator.py --price {{price}} --true-prob {{true_prob}} --side SELL --bankroll {{bankroll}}
