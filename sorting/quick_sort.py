def quick_sort(arr):
    """快速排序：原地分区实现"""
    def _partition(arr, low, high):
        # 选择最右侧元素作为基准
        pivot = arr[high]
        i = low - 1  # i 指向小于 pivot 的最后一个元素

        for j in range(low, high):
            if arr[j] <= pivot:
                i += 1
                arr[i], arr[j] = arr[j], arr[i]

        # 将基准放到正确位置
        arr[i + 1], arr[high] = arr[high], arr[i + 1]
        return i + 1

    def _quick_sort(arr, low, high):
        if low < high:
            # 分区
            pi = _partition(arr, low, high)
            # 分别对左右两部分递归排序
            _quick_sort(arr, low, pi - 1)
            _quick_sort(arr, pi + 1, high)

    _quick_sort(arr, 0, len(arr) - 1)
    return arr


def quick_sort_simple(arr):
    """快速排序：简洁版（非原地，返回新列表）"""
    if len(arr) <= 1:
        return arr
    pivot = arr[len(arr) // 2]
    left = [x for x in arr if x < pivot]
    middle = [x for x in arr if x == pivot]
    right = [x for x in arr if x > pivot]
    return quick_sort_simple(left) + middle + quick_sort_simple(right)


if __name__ == "__main__":
    # 测试
    test_arr = [3, 6, 8, 10, 1, 2, 1]
    print(f"排序前: {test_arr}")

    arr1 = test_arr.copy()
    quick_sort(arr1)
    print(f"原地排序: {arr1}")

    arr2 = test_arr.copy()
    result = quick_sort_simple(arr2)
    print(f"简洁版排序: {result}")
