def calculate_rber_72_layer_tlc(cycles, time, reads):
    epsilon = 1.48e-03  # Base error
    # Wear-out coef
    alpha = 3.90e-10
    k = 2.05
    
    # Retention coef
    beta = 6.28e-05
    m = 0.14
    n = 0.54
    
    # Disturbance coef
    gamma = 3.73e-09
    p = 0.33
    q = 1.71
    
    total_rber = epsilon + alpha * (cycles ** k) + beta * (cycles ** m) * (time ** n) + gamma * (cycles ** p) * (reads ** q)
    
    return total_rber