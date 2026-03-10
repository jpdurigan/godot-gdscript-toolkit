func a():
	var b  # breaking comments conventions
	var ccccc  # breaking comments conventions
	
	var test = c(b, ccccc, b)


# gdformat: off
func b():
	var b      # breaking comments conventions
	var ccccc  # breaking comments conventions

	var test = c(
		b,
		ccccc,
		b
	)
# gdformat: on


func c():
	var b  # breaking comments conventions
	var ccccc  # breaking comments conventions
	
	var test = c(b, ccccc, b)


# gdformat: off
func d():
	pass




func e():
	pass
# gdformat: on
