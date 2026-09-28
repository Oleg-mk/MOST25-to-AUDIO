// ain.c - see ain.h.
#include "ain.h"

void ain_init(ain_t *a)
{
    a->run = a->locked = a->npcm = 0;
    a->since = a->low_at = 0;
}

int ain_pick(ain_t *a, int streaming, int err, int npcm, int64_t now)
{
    a->npcm = npcm;
    if (npcm) {
        a->run = 0;
    } else if (!err) {
        if (!a->run) {
            a->run = 1;
            a->since = now;
        }
        a->low_at = now;
    } else if (a->run && now - a->low_at >= AIN_LOST_US) {
        a->run = 0;
    }
    a->locked = a->run && now - a->since >= AIN_SETTLE_US;
    return streaming ? AIN_PHONE : a->locked ? AIN_TOSLINK : AIN_NONE;
}
