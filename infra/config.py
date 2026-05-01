# Redis connection
REDIS_HOST = "127.0.0.1"
REDIS_PORT = 6379
# REDIS_DB   = 0

# Redis key names
QUEUE_KEY      = "task_queue"
PROCESSING_KEY = "processing:{}"   # .format(task_id)

# ------------------------------------------------------------------ #
#  Timing constants                                                   #
#                                                                     #
#  Relationship that must hold for correct failure detection:         #
#                                                                     #
#    PROCESSING_TTL > HEARTBEAT_INTERVAL                              #
#      - TTL must outlive at least one heartbeat renewal,             #
#        otherwise a healthy worker's key expires mid-task.           #
#                                                                     #
#    EXPIRY_CHECK_THRESHOLD > SCAN_INTERVAL                           #
#      - Watchdog catches keys that will expire before the next scan. #
#        BUFFER absorbs scheduling jitter.                            #
#                                                                     #
#    PROCESSING_TTL - HEARTBEAT_INTERVAL > EXPIRY_CHECK_THRESHOLD     #
#      - Prevent expiry checks from flagging false positives          #
#        (keys at the bottom of their ttl heartbeat cycle)            #
# ------------------------------------------------------------------ #

HEARTBEAT_INTERVAL     = 5   # seconds between worker TTL renewals
SCAN_INTERVAL          = 3   # seconds between watchdog scans
BUFFER                 = 2   # scheduling jitter margin (seconds)
BRPOP_TIMEOUT          = 5   # seconds a worker blocks on an empty queue

EXPIRY_CHECK_THRESHOLD = SCAN_INTERVAL + BUFFER
PROCESSING_TTL         = HEARTBEAT_INTERVAL + EXPIRY_CHECK_THRESHOLD + BUFFER

# ------------------------------------------------------------------ #
#  Worker behaviour                                                   #
# ------------------------------------------------------------------ #

MAX_IDLE_CYCLES = 3   # consecutive empty POPs before a worker exits


# ------------------------------------------------------------------ #
#  Task behaviour                                                   #
# ------------------------------------------------------------------ #

TASK_COMPLETION_TIME = 7
