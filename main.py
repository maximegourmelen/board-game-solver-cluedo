import pandas as pd
import os
import time


class Player:
    def __init__(self, name):
        self.name = name
        self.guesses = 0
    



def play_game():
    print('\n')
    print('Welcome to Cluedo solver.')
    print('Remember to enter your name as the first player.')
    print('\n')
    number_of_players = int(input("Number of players: "))
    print('Number of players recorded.')

    
    player_list = []    
    for i in range(number_of_players):
        player_list.append(str(input(f"Player {i+1}: ")))
    print(f"Names of players recorded {player_list}.")

    guesses_dict = {f'{player_list[i]}': 0 for i in range(len(player_list))}

    print(guesses_dict)
    player_list += ["pool", "envelope"]
    attributes = ["mustard", "plum", "green", "peacock", "scarlet", "white", 
                  "knife", "candlestick", "pistol", "poison", "trophy", "rope", "bat", "ax", "dumbbell",
                  "hall", "dining room", "kitchen", "patio", "observatory", "theater", "living room", "spa", "guest house"]

    d = {f'{player_list[i]}':['-' for _ in range(len(attributes))] for i in range(len(player_list))}
    df = pd.DataFrame(d, index=attributes)

    #
    # Remove rows of known cards
    #
    def log_cards(n):
        card_list = []
        for i in range(n):
            card = None
            card = str(input(f"Enter card #{i+1}: "))
            while card not in attributes:
                print("You entered an invalid card, please try again.")
                card = str(input(f"Enter card #{i+1}: "))
            card_list.append(card)
        return card_list
            
    number_of_cards = int(input("How many cards do you have in your hands: "))
    kill_attributes = log_cards(number_of_cards)
    
    for i in range(number_of_cards):
        df.at[kill_attributes[i], 'envelope'] = 'X'
        df.at[kill_attributes[i], player_list[0]] = 'O'

    # df.drop(kill_attributes, inplace=True)

    def check_df():
    
        for player in player_list[:number_of_players]:
            guess_numbers = []
            loc_dict = {}
            for attribute in attributes:
                try:
                    temp_guess_numbers = df.at[attribute, player].split(',')
                    del temp_guess_numbers[-1]
                    guess_numbers += temp_guess_numbers
                except Exception as e:
                    pass
            no_duplicates_guess_numbers = list(dict.fromkeys(guess_numbers))
            guess_number_to_remove = []
            for element in no_duplicates_guess_numbers:
                count = 0
                for number in guess_numbers:
                    if number == element:
                        count += 1
                if count == 1:
                    guess_number_to_remove.append(element)
            
            for number in guess_number_to_remove:
                for attribute in attributes:
                    temp_guess_numbers = df.at[attribute, player].split(',')
                    del temp_guess_numbers[-1]
                    if number in temp_guess_numbers:
                        df.at[attribute, player] = 'O'
        for attribute in attributes:
            for player in player_list[:number_of_players+1]:
                player_with_O = None
                if df.at[attribute, player] == 'O':
                    player_with_O = str(player)
                    other_players = player_list[:-1]
                    other_players.remove(player_with_O)
                    for sub_player in other_players:
                        df.at[attribute, sub_player] = 'X'
                if df.at[attribute, player] == 'O':
                    df.at[attribute, 'envelope'] = 'X'
                
        for player in player_list[:number_of_players]:
            count_O = 0
            count_X = 0
            for attribute in attributes:
                if df.at[attribute, player] == 'O':
                    count_O += 1
                elif df.at[attribute, player] == 'X':
                    count_X += 1
            if count_O == number_of_cards:
                for attribute in attributes:
                    if df.at[attribute, player] != 'O':
                        df.at[attribute, player] = 'X'
            elif count_X == 25 - number_of_cards:
                if df.at[attribute, player] != 'X':
                        df.at[attribute, player] = 'O'
            
        

    def play_round():
        print(f'Here is the list of players: {player_list[:number_of_players]}')
        log_player_name = str(input("Enter the player's name who's cards you might know: "))

        if log_player_name == 'pool':
            number_of_cards_in_pool = int(input("How many cards are in the pool: "))
            log_player_cards = log_cards(number_of_cards_in_pool)
            for attribute in attributes:
                df.at[attribute, 'pool'] = 'X'
            for i in range(len(log_player_cards)):
                df.at[log_player_cards[i], 'pool'] = 'O'
            return None
        know_or_dknow = str(input("Enter 't' the person has the cards, enter 'f' if the person doesn't have the cards, enter 'q' if you are sure of the card: "))
        if know_or_dknow == 'q':
            log_player_cards = log_cards(1)
            df.at[log_player_cards[0], log_player_name] = 'O'
            return None
        log_player_cards = log_cards(number_of_cards)
        add_to_dict = False
        if know_or_dknow == 'f':
            for i in range(number_of_cards):
                df.at[log_player_cards[i], log_player_name] = 'X'

        else:
            for i in range(number_of_cards):
                if df.at[log_player_cards[i], log_player_name] == '-':
                    df.at[log_player_cards[i], log_player_name] = ''
                    df.at[log_player_cards[i], log_player_name] += str(str(guesses_dict[log_player_name]) + ",")
                    add_to_dict = True

        if add_to_dict == True:    
            guesses_dict[log_player_name] += 1

    def probability():
        guest_count = 0
        weapons_count = 0
        rooms_count = 0
        
        guest_attributes = attributes[:-18]
        weapons_attributes = attributes[6:15]
        rooms_attributes = attributes[15:25]
        for attribute in guest_attributes:
            if df.at[attribute, 'envelope'] == 'X':
                guest_count += 1
        for attribute in weapons_attributes:
            if df.at[attribute, 'envelope'] == 'X':
                weapons_count += 1
        for attribute in rooms_attributes:
            if df.at[attribute, 'envelope'] == 'X':
                rooms_count += 1

        guest_prob =  1 / (6 - guest_count) 
        weapons_prob =  1 / (9 - weapons_count)
        rooms_prob =  1 / (9 - rooms_count) 
        print(f'Your chance of winning by guessing randomly is: {round(guest_prob * weapons_prob * rooms_prob * 100, 2)}%.')

    def spaces():
        for _ in range(3):
            print('\n')
        return None

    while True:
        
        probability()
        spaces()
        play_round()
        for _ in range(20):
            check_df()
        print(df)
        spaces()


play_game()