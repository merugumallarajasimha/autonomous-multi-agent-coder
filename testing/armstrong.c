#include <stdio.h>

int is_armstrong(int num) {
    int original_num, remainder, result = 0, n = 0;
    original_num = num;

    // Count the number of digits
    while (original_num != 0) {
        original_num /= 10;
        ++n;
    }

    original_num = num;

    // Calculate the sum of digits raised to the power n
    while (original_num != 0) {
        remainder = original_num % 10;
        result += remainder * remainder * remainder;
        original_num /= 10;
    }

    // Check if the result is equal to the original number
    if (result == num)
        return 1;
    else
        return 0;
}

int main() {
    int num;
    printf("Enter a number: ");
    scanf("%d", &num);

    if (is_armstrong(num))
        printf("%d is an Armstrong number.
", num);
    else
        printf("%d is not an Armstrong number.
", num);

    return 0;
}