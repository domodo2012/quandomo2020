def iterate_for_static_list_length(l):
    for i in range(len(l)):
        yield i
        l.append(object())


def iterate_for_dynamic_list_length(l):
    for i, _ in enumerate(l):
        yield i
        l.append(object())


if __name__ == '__main__':
    l = [object()] * 3

    print('Static implementation')
    for value in iterate_for_static_list_length(l):
        input(value)

    print('\nDynamic implementation')
    for value in iterate_for_dynamic_list_length(l):
        input(value)
