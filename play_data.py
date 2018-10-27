import requests
import logging
import pandas as pd
import numpy as np


logger = logging.getLogger(__name__)

def get_json_data(game_id):
    response = requests.get(
        'http://cdn.espn.com/core/college-football/playbyplay?gameId={}&xhr=1&render=false&userab=18'.format(game_id))
    data = response.json()
    return data


def get_team_data(data):
    u_dict = {}
    away = {
        "displayName": data['__gamepackage__']['awayTeam']['team']['displayName'],
        "abv": data['__gamepackage__']
                ['awayTeam']['team']['abbreviation']}

    home = {
        "displayName": data['__gamepackage__']['homeTeam']['team']['displayName'],
        "abv": data['__gamepackage__']
                ['homeTeam']['team']['abbreviation']}

    u_dict['awayTeam'] = away
    u_dict['homeTeam'] = home

    return u_dict


def get_clean_play_data(drive_data, awayTeam, homeTeam, possTeam):
    drive_list = []
    for d in drive_data:
        u_dict = {}
        home_score = "{}_score".format(homeTeam)
        away_score = "{}_score".format(awayTeam)
        u_dict[home_score] = d['homeScore']
        u_dict[away_score] = d['awayScore']
        u_dict['quarter'] = d['period']['number']
        u_dict['clock'] = d['clock']['displayValue']
        u_dict['endDown'] = d['end']['down']
        u_dict['endDistance'] = d['end']['distance']
        u_dict['possession'] = possTeam
        if 'startDownDistanceText' in d['end'].keys():
            u_dict['endDownDistanceText'] = d['end']['shortDownDistanceText']
        if 'possessionText' in d['end'].keys():
            u_dict['endPossessionText'] = d['end']['possessionText']
        u_dict['endYardLine'] = d['end']['yardLine']
        u_dict['endYardsToEndzone'] = d['end']['yardsToEndzone']
        u_dict['text'] = d['text']
        u_dict['statYardage'] = d['statYardage']
        if 'abbreviation' in d['type'].keys():
            type_abv = d['type']['abbreviation']
            type_text = d['type']['text']
            u_dict['type_abv'] = get_td_play_type(type_abv, type_text)
        if 'text' in d['type'].keys():
            u_dict['type_text'] = d['type']['text']
        u_dict['startDown'] = d['start']['down']
        u_dict['startDistance'] = d['start']['distance']
        if 'shortDownDistanceText' in d['start'].keys():
            u_dict['startDownDistanceText'] = d['start']['shortDownDistanceText']
        if 'possessionText' in d['start'].keys():
            u_dict['startPossessionText'] = d['start']['possessionText']
        u_dict['startYardLine'] = d['start']['yardLine']
        u_dict['startYardsToEndzone'] = d['start']['yardsToEndzone']
        u_dict['scoringPlay'] = d['scoringPlay']
        drive_list.append(u_dict)
    return drive_list


def get_td_play_type(type_abv, type_text):
    if type_abv == 'TD':
        if type_text.split()[0] == 'Passing':
            return 'REC'
        elif type_text.split()[0] == 'Rushing':
            return 'RUSH'
    return type_abv

def clean_all_drives(json, awayTeam, homeTeam):
    data = json['gamepackageJSON']['drives']
    if 'previous' in data.keys():
        drives = data['previous']
        play_by_play = []
        for d in drives:
            possTeam = d['team']['abbreviation']
            clean_drives = get_clean_play_data(d['plays'], awayTeam, homeTeam, possTeam)
            play_by_play = play_by_play + clean_drives
        return play_by_play
    elif 'drives' in data.keys():
        drives = data['current']
        play_by_play = []
        for d in drives:
            possTeam = d['team']['abbreviation']
            clean_drives = get_clean_play_data(d['plays'], awayTeam, homeTeam, possTeam)
            play_by_play = play_by_play + clean_drives
        return play_by_play
    logger.error("No drives found")

def success_rate_bool(statYardage, startDown, startDistance, type_abv):
    if type_abv == "REC" or type_abv == "RUSH":
        if startDown == 1:
            suc_yards = round(startDistance / 2,0)
        elif startDown == 2:
            suc_yards = round(startDistance * 0.7, 0)
        else:
            suc_yards = startDistance

        if statYardage >= suc_yards:
            return True
        return False
    return np.nan

def garbage_time_calc(homeScore, awayScore, quarter):
    score_margin = abs(homeScore - awayScore)
    if quarter == 2 and score_margin > 38:
        return True
    elif quarter == 3 and score_margin > 28:
        return True
    elif quarter == 4 and score_margin > 22:
        return True
    return False

def line_yards_calc(type_abv, statYardage):
    if type_abv == "RUSH":
        if statYardage < 0:
            lineYards = statYardage * 1.25
        elif statYardage < 4:
            lineYards = statYardage
        elif statYardage < 7:
            midYards = (statYardage - 6) / 2
            lineYards = 3 + midYards
        else:
            lineYards = 5
        return lineYards
    return 0


def hlt_yards_calc(type_abv, line_yards, statYardage):
    if type_abv == "RUSH":
        if statYardage < 0:
            hltYards = 0
        hltYards = statYardage - line_yards
        return hltYards
    return 0


def stuff_rt_calc(type_abv, statYardage):
    if type_abv == "RUSH":
        if statYardage < 0:
            return True
        return False
    return False

def down_type_calc(down, distance):
    if down == 1:
        return 'STD'
    elif down == 2 and distance < 8:
        return 'STD'
    elif down == 3 or down == 4 and distance < 5:
        return 'STD'
    return 'PASS'

def add_adv_stats(df, away_abv, home_abv):
    df['successPlay'] = df.apply(
        lambda row: success_rate_bool(
            row['statYardage'], row['startDown'], row['startDistance'], row['type_abv']
        ), axis=1)

    homeScore = "{}_score".format(home_abv)
    awayScore = "{}_score".format(away_abv)

    df['garbageBool'] = df.apply(
        lambda row: garbage_time_calc(row[homeScore], row[awayScore], row['quarter']), axis=1
    )

    df['lineYards'] = df.apply(
        lambda row: line_yards_calc(row['type_abv'], row['statYardage']), axis=1
    )

    df['highlightYards'] = df.apply(
        lambda row: hlt_yards_calc(row['type_abv'], row['lineYards'], row['statYardage']), axis=1
    )

    df['stuffRate'] = df.apply(
        lambda row: stuff_rt_calc(row['type_abv'], row['statYardage']), axis=1
    )

    df['downType'] = df.apply(
        lambda row: down_type_calc(row['startDown'], row['startDistance']), axis=1
    )

    return df

def make_df(gameId):
    json_data = get_json_data(gameId)
    team_dict = get_team_data(json_data)
    away_abv = team_dict['awayTeam']['abv']
    home_abv = team_dict['homeTeam']['abv']
    all_play_by_play = clean_all_drives(json_data, away_abv, home_abv)

    df = pd.DataFrame(all_play_by_play)
    df = add_adv_stats(df, away_abv, home_abv)

    return df


def suc_by_qtr(df):
    return df.groupby(['possession', 'quarter'])['successPlay'].apply(lambda x: x[x == True].count() / x.count())

def suc_overall(df):
    return df.groupby(['possession'])['successPlay'].apply(lambda x: x[x == True].count() / x.count())

def suc_down_type(df):
    return df.groupby(['possession', 'downType'])['successPlay'].apply(lambda x: x[x == True].count() / x.count())

def suc_play_type(df):
    return df.groupby(['possession', 'type_abv'])['successPlay'].apply(lambda x: x[x == True].count() / x.count())
