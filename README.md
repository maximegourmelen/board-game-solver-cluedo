# Cluedo Assistant

A Python command-line helper that uses elimination and probability tracking to deduce the cards in the case file and dramatically increase your chances of winning Cluedo (Clue).

## Features

- Record number of players and their names  
- Log your own cards and track each suggestion’s responses  
- Maintain a DataFrame of possible cards for each player and the envelope  
- Apply elimination rules to mark impossible cards (“X”) and confirmed cards (“O”)  
- Continuously recompute probabilities as you log more information  
- Show you, at any point, which combination of suspect, weapon, and room remains most likely  

## Installation

1. Clone this repository:
   ```bash
   git clone https://github.com/maximegourmelen/board-game-solver-cluedo.git
   cd cluedo-assistant
