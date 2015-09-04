//#include "agelib.h"
//#include <string.h>
#include <stdio.h>

char buffer[100]

char * main(int z) {

    if (z > 700)
        return "2 years...";
    else if (z > 365)
        return "A year +";
    else if (z > 60)
        return snprintf (buffer, 99, "%d months", z/30);
    else if (z > 40)
        return snprintf (buffer, 99, "%d weeks", z/7);
    else if (z > 27)
        return "1 month";
    else if (z >13)
        return snprintf (buffer, 99, "%d weeks", z/7);
    else if (z > 6)
        return "1 week";
    else if (z > 1)
        return snprintf (buffer, 99, "%d days", z/7);
    elif z == 1:
        return "yesterday"
    else:
        return "today"
