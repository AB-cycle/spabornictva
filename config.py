class Configuration(object):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = 'mysql+mysqlconnector://root:@localhost/Ab_spab?charset=utf8mb4'

    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,     # Проверка соединения перед использованием
        'pool_size': 10,
        'pool_recycle': 280,
        'max_overflow': 5
    }


    SQLALCHEMY_BINDS = {
        # Если вам нужны отдельные привязки, вы можете их указать
        'gpx': 'mysql+mysqlconnector://root:@localhost/Ab_spab',
        'challenge': 'mysql+mysqlconnector://root:@localhost/Ab_spab',
        'challenge_participants': 'mysql+mysqlconnector://root:@localhost/Ab_spab',
    }
    SQLALCHEMY_TRACK_MODIFICATIONS = False