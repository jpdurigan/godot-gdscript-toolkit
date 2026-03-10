extends Node

var list: Array = []


func _ready() -> void:
	for i in range(5):
		var x := X.new()
		
		# call foo
		x.foo()
		
		# call bar
		x.bar()


class X:
	func foo():
		pass
	
	func bar():
		pass
