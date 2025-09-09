func test(a, b, c) -> void:
	var test_condition: bool = (
		# Condition A
		not really_really_really_really_really_really_long_func(a)
		and (
			# Condition B
			really_really_really_really_really_really_long_func(b)
			# Condition C
			or really_really_really_really_really_really_long_func(c)
		)
	)


func really_really_really_really_really_really_long_func(x) -> bool:
	return x != null
