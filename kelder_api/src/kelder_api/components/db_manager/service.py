

# TODO: does this need to be an ABC
class DBManager:
    """Managers context to manipulate the sqlite dbs. 
    DBs:
        - journey_times: Overall stats of each journey.
        - trip track: Specific data logged throughout a journey.    
    """

    def __init__(self):
        