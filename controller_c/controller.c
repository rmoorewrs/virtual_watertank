#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <unistd.h>
#include <curl/curl.h>
#include <cjson/cJSON.h>

#define DEFAULT_LEVEL_SETPOINT 50
#define DEFAULT_LEVEL_DELTA 20
#define DEFAULT_LEVEL_INCREMENT 1
#define DEFAULT_UPDATE_PERIOD 2000000
#define DEFAULT_CONFIG_FILENAME "config.ini"

#define LEVEL_ABS_MIN 0
#define LEVEL_ABS_MAX 100

struct Memory {
    char *data;
    size_t size;
};

// possible actions/directions
typedef enum {
    FILL,
    DRAIN,
    UNKNOWN_DIRECTION
} dir_state_t;

char *dir_state_strings[] = {"FILL","DRAIN","UNKNOWN_DIRECTION",NULL}; 


// possible tank states
typedef enum {
    OVERFILL,
    LIMITHIGH,
    PARTIAL,
    LIMITLOW,
    UNDERFILL,
    UNKNOWN_STATE
} tank_state_t;

char *tank_state_strings[] = { "OVERFILL","LIMITHIGH","PARTIAL","LIMITLOW","UNDERFILL","UNKNOWN_STATE",NULL};

// structure to hold watertank state and parameters
typedef struct {

    tank_state_t tank_state; // stores the current tank fill state
    dir_state_t dir_state;  // stores the current direction: filling or draining
    int level_actual;   // last measured level
    int level_setpoint; // setpoint goal for the level
    int level_delta;    // deviation from the setpoint
    int level_increment; // incremental change to the level
    useconds_t update_period; // update period in seconds

    // curl functions and API endpoints
    CURL *level_curl;
    CURL *fill_curl;
    CURL *drain_curl;
    
    char *api_url;
    char *level_url;
    char *fill_url;
    char *drain_url;

} watertank_t;

typedef struct {
    char tank_ipaddress[64];
    int tank_port;
    int setpoint;
    int delta;
    int increment;
    useconds_t update_period;
} controller_config_t;

static int build_url(char **out, const char *ip, int port, const char *path) {
    int needed = snprintf(NULL, 0, "http://%s:%d/%s", ip, port, path);
    if (needed < 0) {
        return -1;
    }

    *out = malloc((size_t)needed + 1);
    if (*out == NULL) {
        return -1;
    }

    snprintf(*out, (size_t)needed + 1, "http://%s:%d/%s", ip, port, path);
    return 0;
}

static int parse_int_value(const char *value, int *out) {
    char *endptr = NULL;
    long v = strtol(value, &endptr, 10);
    if (endptr == value || *endptr != '\0') {
        return -1;
    }
    *out = (int)v;
    return 0;
}

static int load_config(controller_config_t *cfg, const char *config_filename) {
    FILE *fp = fopen(config_filename, "r");
    char line[256];
    int have_ip = 0, have_port = 0, have_setpoint = 0;
    int have_delta = 0, have_increment = 0, have_update_period = 0;

    if (fp == NULL) {
        fprintf(stderr, "Failed to open %s: %s\n", config_filename, strerror(errno));
        return -1;
    }

    while (fgets(line, sizeof(line), fp) != NULL) {
        char key[128];
        char value[128];

        if (line[0] == '#' || line[0] == '\n') {
            continue;
        }

        if (sscanf(line, " %127[^=]=%127s", key, value) != 2) {
            continue;
        }

        if (strcmp(key, "tank_ipaddress") == 0) {
            size_t value_len = strlen(value);
            if (value_len >= sizeof(cfg->tank_ipaddress)) {
                fprintf(stderr, "tank_ipaddress too long in %s\n", config_filename);
                fclose(fp);
                return -1;
            }
            memcpy(cfg->tank_ipaddress, value, value_len + 1);
            have_ip = 1;
        } else if (strcmp(key, "tank_port") == 0) {
            have_port = (parse_int_value(value, &cfg->tank_port) == 0);
        } else if (strcmp(key, "setpoint") == 0) {
            have_setpoint = (parse_int_value(value, &cfg->setpoint) == 0);
        } else if (strcmp(key, "delta") == 0) {
            have_delta = (parse_int_value(value, &cfg->delta) == 0);
        } else if (strcmp(key, "increment") == 0) {
            have_increment = (parse_int_value(value, &cfg->increment) == 0);
        } else if (strcmp(key, "update_period") == 0) {
            int period = 0;
            if (parse_int_value(value, &period) == 0) {
                cfg->update_period = (useconds_t)period;
                have_update_period = 1;
            }
        }
    }

    fclose(fp);

    if (!have_ip || !have_port || !have_setpoint || !have_delta || !have_increment || !have_update_period) {
        fprintf(stderr, "Missing required keys in %s\n", config_filename);
        return -1;
    }

    return 0;
}


void print_watertank_t(watertank_t *t) {
    printf("tank_state = %d = %s\n",t->tank_state, tank_state_strings[t->tank_state]);
    printf("dir_state = %d = %s\n",t->dir_state, dir_state_strings[t->dir_state]);
    printf("level_actual = %d\n",t->level_actual);
    printf("level_setpoint = %d\n",t->level_setpoint);
    printf("level_delta = %d\n",t->level_delta);
    printf("level_increment = %d\n",t->level_increment);
    printf("update_period = %u (usec) = %.3f sec\n",
           (unsigned int)t->update_period,
           (double)t->update_period / 1000000.0);

}

static size_t write_callback(void *contents, size_t size, size_t nmemb, void *userp) {
    size_t realsize = size * nmemb;
    struct Memory *mem = (struct Memory *)userp;

    char *new_data = realloc(mem->data, mem->size + realsize + 1);
    if (new_data == NULL) {
        return 0;
    }

    mem->data = new_data;
    memcpy(&(mem->data[mem->size]), contents, realsize);
    mem->size += realsize;
    mem->data[mem->size] = '\0';

    return realsize;
}

// read the level from the watertank
static int get_level(watertank_t *watertank) {
    CURLcode res = -1;
    CURLcode curl_res = -1;
    long http_code = 0;
    struct Memory response = {0};
    CURL *curl = watertank->level_curl; 

    // GET level JSON and parse it with cJSON.
    curl_easy_setopt(curl, CURLOPT_URL, watertank->level_url);
    curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, write_callback);
    curl_easy_setopt(curl, CURLOPT_WRITEDATA, (void *)&response);

    res = curl_easy_perform(watertank->level_curl);
    if (res != CURLE_OK) {
        fprintf(stderr, "GET failed: %s\n", curl_easy_strerror(curl_res));
        free(response.data);
        return -1;
    }

    curl_easy_getinfo(curl, CURLINFO_RESPONSE_CODE, &http_code);
    if (http_code != 200 && http_code != 201) {
        fprintf(stderr, "GET returned HTTP %ld\n", http_code);
        free(response.data);
        return -1;
    }

    cJSON *root = cJSON_Parse(response.data);
    if (root == NULL) {
        fprintf(stderr, "Invalid JSON response: %s\n", response.data ? response.data : "(null)");
        free(response.data);
        return -1;
    }

    cJSON *level_item = cJSON_GetObjectItemCaseSensitive(root, "level");
    if (!cJSON_IsNumber(level_item)) {
        fprintf(stderr, "JSON does not contain numeric 'level': %s\n", response.data);
        cJSON_Delete(root);
        free(response.data);
        return -1;
    }

    int level = level_item->valueint;
    cJSON_Delete(root);
    free(response.data);
    watertank->level_actual = level;
    return level;
}

// compute level_low -- it can changed dynamically
int level_low(watertank_t *watertank){
    int low = watertank->level_setpoint - watertank->level_delta;
    if (low < LEVEL_ABS_MIN)
        low = LEVEL_ABS_MIN;
    return low;
}

// compute level_high -- it can changed dynamically
int level_high(watertank_t *watertank){
    int high = watertank->level_setpoint + watertank->level_delta;
    if (high > LEVEL_ABS_MAX)
        high = LEVEL_ABS_MAX;
    return high;
}

// drain or fill the watertank using parameters set in the watertank object
static int tank_fill_or_drain(watertank_t *watertank) {
    CURLcode res;
    CURL *curl = watertank->fill_curl;
    long http_code = 0;
    struct curl_slist *headers = NULL;
    cJSON *body = NULL;
    char *payload = NULL;

    body = cJSON_CreateObject();
    if (body == NULL) {
        fprintf(stderr, "tank_fill_or_drain: Failed to create JSON body\n");
        return -1;
    }
    if (cJSON_AddNumberToObject(body, "delta_level", watertank->level_increment) == NULL) {
        fprintf(stderr, "tank_fill_or_drain: Failed to set delta_level in JSON body\n");
        cJSON_Delete(body);
        return -1;
    }
    payload = cJSON_PrintUnformatted(body);
    cJSON_Delete(body);
    if (payload == NULL) {
        fprintf(stderr, "tank_fill_or_drain: Failed to serialize JSON body\n");
        return -1;
    }

    headers = curl_slist_append(headers, "Content-Type: application/json");
    if (headers == NULL) {
        fprintf(stderr, "tank_fill_or_drain: Failed to allocate HTTP headers\n");
        return -1;
    }

    if (watertank->dir_state == FILL) {
        curl_easy_setopt(curl, CURLOPT_URL, watertank->fill_url);
    } else if (watertank->dir_state == DRAIN) {
        curl_easy_setopt(curl, CURLOPT_URL, watertank->drain_url);
    } else {
        fprintf(stderr, "tank_fill_or_drain: Invalid action: %d\n", watertank->dir_state);
        return -1;
    }

    curl_easy_setopt(curl, CURLOPT_POST, 1L);
    curl_easy_setopt(curl, CURLOPT_HTTPHEADER, headers);
    curl_easy_setopt(curl, CURLOPT_POSTFIELDS, payload);
    curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, NULL);
    curl_easy_setopt(curl, CURLOPT_WRITEDATA, stdout);

    res = curl_easy_perform(curl);
    if (res != CURLE_OK) {
        fprintf(stderr, "tank_fill_or_drain: POST failed: %s\n", curl_easy_strerror(res));
        curl_slist_free_all(headers);
        free(payload);
        return -1;
    }

    curl_easy_getinfo(curl, CURLINFO_RESPONSE_CODE, &http_code);
    curl_slist_free_all(headers);
    free(payload);
    if (http_code != 200 && http_code != 201) {
        fprintf(stderr, "tank_fill_or_drain: POST returned HTTP %ld\n", http_code);
        return -1;
    }

    return 0;
}

int controller_init(watertank_t *watertank, const char *config_filename) {
    CURLcode init_res;
    controller_config_t cfg = {0};

    // init watertank object to illegal values for checking config file success
    watertank->level_actual=watertank->level_setpoint=watertank->level_delta=watertank->level_increment= -1;
    watertank->update_period= 0;
    watertank->level_curl=watertank->fill_curl=watertank->drain_curl=watertank->api_url=watertank->level_url =watertank->fill_url=watertank->drain_url= NULL;

    // make sure config filename is set
    if (config_filename == NULL)
        config_filename = DEFAULT_CONFIG_FILENAME;

    init_res = curl_global_init(CURL_GLOBAL_DEFAULT);
    if ( init_res != CURLE_OK) {
        fprintf(stderr, "Failed to init curl globals: %s\n", curl_easy_strerror(init_res));
        return -1;
    }

    watertank->level_curl = curl_easy_init();
    watertank->fill_curl = curl_easy_init();
    watertank->drain_curl = curl_easy_init();
    if (watertank->level_curl == NULL || watertank->fill_curl == NULL || watertank->drain_curl == NULL) {
        fprintf(stderr, "Failed to init one or more CURL handles\n");
        curl_global_cleanup();
        return -1;
    }

    if (load_config(&cfg, config_filename) != 0) {
        curl_easy_cleanup(watertank->level_curl);
        curl_easy_cleanup(watertank->fill_curl);
        curl_easy_cleanup(watertank->drain_curl);
        curl_global_cleanup();
        return -1;
    }

    // did all values get set from the config file? if not apply defaults
    if (watertank->level_setpoint < 0)
        watertank->level_setpoint = DEFAULT_LEVEL_SETPOINT;
    if (watertank->level_delta < 0)
        watertank->level_delta = DEFAULT_LEVEL_DELTA;
    if (watertank->level_increment < 0)
        watertank->level_increment = DEFAULT_LEVEL_INCREMENT;
    if (watertank->update_period == 0)
        watertank->update_period = DEFAULT_UPDATE_PERIOD;

    // set the URL endpoints for the watertank API
    if (build_url(&watertank->api_url, cfg.tank_ipaddress, cfg.tank_port, "") != 0 ||
        build_url(&watertank->level_url, cfg.tank_ipaddress, cfg.tank_port, "level") != 0 ||
        build_url(&watertank->fill_url, cfg.tank_ipaddress, cfg.tank_port, "fill") != 0 ||
        build_url(&watertank->drain_url, cfg.tank_ipaddress, cfg.tank_port, "drain") != 0) {
        fprintf(stderr, "Failed to build endpoint URLs from %s\n", config_filename);
        curl_easy_cleanup(watertank->level_curl);
        curl_easy_cleanup(watertank->fill_curl);
        curl_easy_cleanup(watertank->drain_curl);
        free(watertank->api_url);
        free(watertank->level_url);
        free(watertank->fill_url);
        free(watertank->drain_url);
        curl_global_cleanup();
        return -1;
    }

    // set control parameters from config.ini
    watertank->tank_state = UNDERFILL;
    watertank->dir_state = FILL;
    watertank->level_setpoint = cfg.setpoint;
    watertank->level_delta = cfg.delta;
    watertank->level_increment = cfg.increment;
    watertank->update_period = cfg.update_period;

    return 0;
}

tank_state_t compute_tank_state(watertank_t *watertank){
    int high,low = 0;
    watertank->level_actual = get_level(watertank);
    high = level_high(watertank);
    low = level_low(watertank);

    if (watertank->level_actual < low)
        watertank->tank_state = UNDERFILL;
    else if (watertank->level_actual == low)
        watertank->tank_state = LIMITLOW;
    else if (watertank->level_actual == LIMITHIGH)
        watertank->tank_state = LIMITHIGH;
    else if (watertank->level_actual > high)
        watertank->tank_state = OVERFILL;
    else
        watertank->tank_state = PARTIAL;

    return watertank->tank_state;

}



// main task that does the control cycle
int cycle_task(watertank_t *watertank) {
    tank_state_t tank_state = UNKNOWN_STATE;
    int rv=0;
    
    // compute the next state
    tank_state = compute_tank_state(watertank);
    switch (tank_state){
    
        case OVERFILL:
            watertank->dir_state = DRAIN;
            tank_fill_or_drain(watertank);
            printf("cycle_task() correcting OVERFILL\n");
            break;

        case UNDERFILL:
            watertank->dir_state = FILL;
            tank_fill_or_drain(watertank);
            printf("cycle_task() correcting UNDERFILL\n");
            break;

        // LIMITHIGH 
        case LIMITHIGH:
            // NOTE: switching directions
            watertank->dir_state = DRAIN;
            tank_fill_or_drain(watertank);
            printf("cycle_task(): LIMITHIGH->DRAIN\n");
            break;

        // LIMITLOW
        case LIMITLOW:
            // NOTE: switching directions
            watertank->dir_state = FILL;
            tank_fill_or_drain(watertank);
            printf("cycle_task(): LIMITLOW->FILL\n");
            break;

        // PARTIAL, meaning in between LIMITHIGH and LIMITLOW
        case PARTIAL:
            // fill or drain, per the current direction
            tank_fill_or_drain(watertank);
            printf("cycle_task(): PARTIAL\n");
            break;

        default:
            printf("cycle_task(): ILLEGAL STATE\n");
            rv= -1;
            break;
    }

    return rv;
}

int main(void) {
    // create and initialize the watertank object
    watertank_t *watertank = malloc(sizeof(watertank_t));
    if (controller_init(watertank, "config.ini") != 0) {
        printf("controller_init() failed, exiting\n");
        return -1;
    }
    print_watertank_t(watertank);

    // run the tank controller
    while (1){
        printf("Tank State=%s, Dir=%s, level = %d, increment=%d%%, low=%d, high=%d\n", 
            tank_state_strings[watertank->tank_state], 
            dir_state_strings[watertank->dir_state],
            watertank->level_actual,
            watertank->level_increment,
            level_low(watertank),
            level_high(watertank)
        );
        if (cycle_task(watertank) != 0)
            break;
        else
            usleep(watertank->update_period);
    }


    curl_easy_cleanup(watertank->level_curl);
    curl_easy_cleanup(watertank->fill_curl);
    curl_easy_cleanup(watertank->drain_curl);
    free(watertank->api_url);
    free(watertank->level_url);
    free(watertank->fill_url);
    free(watertank->drain_url);
    curl_global_cleanup();
    free(watertank);
    return 0;
}