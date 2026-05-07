# Redis connection
REDIS_HOST = "127.0.0.1"
REDIS_PORT = 6379
REDIS_DB = 0

# Redis key names
QUEUE_KEY = "task_queue"
PROCESSING_KEY = "processing:{}"                # .format(task_id)
LEADER_LOCK_KEY = "leader_lock"                 # held by the active leader
LEADER_RUNTIME_KEY = "leader_runtime"           # shared runtime state (store remaining time)
TASKS_REMAINING_KEY = "leader_tasks_remaining"  # counter for remaining tasks

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
#      - Watchdog must not flag healthy workers as expired.           #
#        Healthy worker TTL oscillates in the range:                  #
#          (PROCESSING_TTL - HEARTBEAT_INTERVAL, PROCESSING_TTL]      #
#        Threshold must stay below that lower bound.                  #
# ------------------------------------------------------------------ #

HEARTBEAT_INTERVAL = 5   # seconds between worker TTL renewalsL
SCAN_INTERVAL = 3   # seconds between watchdog scans
BUFFER = 2   # scheduling jitter margin (seconds)
BRPOP_TIMEOUT = 5   # seconds a worker blocks on an empty queue

EXPIRY_CHECK_THRESHOLD = SCAN_INTERVAL + BUFFER
PROCESSING_TTL = HEARTBEAT_INTERVAL + EXPIRY_CHECK_THRESHOLD + BUFFER

# ------------------------------------------------------------------ #
#  Leader election                                                    #
#                                                                     #
#  LEADER_TTL must be long enough for the leader to renew it          #
#  between heartbeats, but short enough that a crashed leader's       #
#  lock expires before standbys give up waiting.                      #
#                                                                     #
#  Same invariant pattern as worker heartbeats:                       #
#    LEADER_TTL > LEADER_HEARTBEAT_INTERVAL                           #
# ------------------------------------------------------------------ #

LEADER_HEARTBEAT_INTERVAL = 3   # seconds between leader lock renewals
LEADER_TTL = 10                 # lock expiry — must be > LEADER_HEARTBEAT_INTERVAL
ELECTION_POLL_INTERVAL = 2      # seconds standbys wait between lock attempts

# ------------------------------------------------------------------ #
#  Worker behaviour                                                   #
# ------------------------------------------------------------------ #

MAX_IDLE_CYCLES = 3         # consecutive empty POPs before a worker exits

# ------------------------------------------------------------------ #
#  Task generation                                                    #
# ------------------------------------------------------------------ #

TASK_DURATION_MIN = 2       # minimum task execution time (seconds)
TASK_DURATION_MAX = 8       # maximum task execution time (seconds)
TASK_INTERVAL_MIN = 0.5     # minimum gap between task generations (seconds)
TASK_INTERVAL_MAX = 3.0     # maximum gap between task generations (seconds)

# ------------------------------------------------------------------ #
#  Crash simulator/ Supervisor                                        #
# ------------------------------------------------------------------ #

CRASH_PROBABILITY = 0.3     # per-process probability of crashing per check interval
CRASH_CHECK_INTERVAL = 5    # seconds between crash probability rolls
SUPERVISOR_INTERVAL = 5     # health check timer for supervisor (starts new worker/leader processes upon crash)

# ------------------------------------------------------------------ #
#  Metrics (Prometheus Client)                                        #
# ------------------------------------------------------------------ #

PROMETHEUS_MULTIPROC_DIR = "/tmp/prometheus_multiproc"
METRICS_PORT = 9191
