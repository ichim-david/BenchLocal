// Example: factorial(5) = 5 * 4 * 3 * 2 * 1 = 120

fn factorial(n: u64) -> u64 {
    if n == 0 {
        1
    } else {
        n * factorial(n - 1)
    }
}

fn main() {
    println!("factorial(10) = {}", factorial(10));
}
