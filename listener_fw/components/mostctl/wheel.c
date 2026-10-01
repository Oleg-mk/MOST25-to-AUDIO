// wheel.c - see wheel.h.
#include "wheel.h"

#include <string.h>

void wheel_init(wheel_t *w)
{
    memset(w, 0, sizeof *w);
}

static int same(const mm_tel_t *a, const mm_tel_t *b)
{
    return a->source == b->source && a->target == b->target && a->fblock == b->fblock && a->inst == b->inst &&
           a->fkt == b->fkt && a->op == b->op && a->len == b->len && !memcmp(a->data, b->data, a->len);
}

int wheel_tel(wheel_t *w, const mm_tel_t *t)
{
    if (t->fkt != WHEEL_FKT)
        return WHEEL_NONE;
    const int again = w->have && same(&w->last, t) && t->frame - w->frame < WHEEL_SAME_FRAMES;
    w->have = 1;
    w->frame = t->frame;
    w->last = *t;
    if (again)
        return WHEEL_NONE;
    if (t->len >= 2 && t->data[0] == 0x03 && t->data[1] == 0x01)
        return WHEEL_NEXT;
    if (t->len >= 3 && t->data[0] == 0x04 && t->data[2] == 0x01)
        return WHEEL_PREV;
    return WHEEL_NONE;
}
