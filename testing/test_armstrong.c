#include <stdio.h>
#include <assert.h>

int is_armstrong(int num);

void test_is_armstrong() {
    assert(is_armstrong(153) == 1);
    assert(is_armstrong(370) == 1);
    assert(is_armstrong(9474) == 1);
    assert(is_armstrong(123) == 0);
    assert(is_armstrong(9475) == 0);
    printf("All tests passed.
");
}

int main() {
    test_is_armstrong();
    return 0;
}