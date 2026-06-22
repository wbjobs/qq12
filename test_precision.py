from services import _kahan_sum, _calculate_group_stats


class MockMember:
    def __init__(self, temp):
        self.current_color_temp = temp


def test_kahan_sum_accuracy():
    print("=== 测试 Kahan 求和算法精度 ===")

    temps = [6500.123] * 10000
    expected = 6500.123 * 10000

    naive_sum = sum(temps)
    kahan_sum = _kahan_sum(temps)

    print(f"预期总和: {expected:.10f}")
    print(f"普通sum:  {naive_sum:.10f} (误差: {abs(naive_sum - expected):.10f})")
    print(f"Kahan:    {kahan_sum:.10f} (误差: {abs(kahan_sum - expected):.10f})")
    print(f"Kahan是否更准确: {abs(kahan_sum - expected) <= abs(naive_sum - expected)}")
    print()

    return abs(kahan_sum - expected) <= abs(naive_sum - expected)


def test_calculate_group_stats_precision():
    print("=== 测试组统计计算精度 ===")

    members = [MockMember(6500.5 + i * 0.1) for i in range(15)]

    avg, diff = _calculate_group_stats(members)

    expected_sum = sum(6500.5 + i * 0.1 for i in range(15))
    expected_avg = expected_sum / 15
    expected_diff = (6500.5 + 14 * 0.1) - 6500.5

    print(f"成员数: {len(members)}")
    print(f"预期平均: {expected_avg:.6f}")
    print(f"实际平均: {avg:.6f}")
    print(f"预期温差: {expected_diff:.6f}")
    print(f"实际温差: {diff:.6f}")
    print(f"平均误差: {abs(avg - expected_avg):.10f}")
    print(f"结果四舍五入到2位小数: {avg}, {diff}")
    print()

    return abs(avg - round(expected_avg, 2)) < 0.01


def test_many_members():
    print("=== 测试大量成员 (100个) ===")

    temps = []
    for i in range(100):
        t = 4000 + i * 25.5
        temps.append(t)

    members = [MockMember(t) for t in temps]
    avg, diff = _calculate_group_stats(members)

    expected_sum = sum(temps)
    expected_avg = expected_sum / len(temps)
    expected_diff = max(temps) - min(temps)

    print(f"成员数: {len(members)}")
    print(f"普通sum平均:    {expected_sum / len(temps):.6f}")
    print(f"Kahan平均:      {avg:.6f}")
    print(f"预期温差: {expected_diff:.2f}")
    print(f"实际温差: {diff:.2f}")
    print(f"结果: avg={avg}, max_diff={diff}")
    print()


if __name__ == "__main__":
    all_passed = True
    all_passed &= test_kahan_sum_accuracy()
    all_passed &= test_calculate_group_stats_precision()
    test_many_members()

    print("=" * 50)
    if all_passed:
        print("所有精度测试通过!")
    else:
        print("部分测试失败!")
