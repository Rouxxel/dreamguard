from dreamguard import demo

LITERAL_BACKSLASH_N = "\\" + "n"


def test_demo_output_has_real_newlines_and_blocks_only_the_unsafe_arm(capsys):
    demo.main()
    output = capsys.readouterr().out

    assert LITERAL_BACKSLASH_N not in output
    assert "Decision: APPROVE" in output
    assert "Decision: BLOCK" in output
    assert "right row 1: joint step" in output
    assert "left row 1" not in output


def test_sample_action_arms_do_not_share_rows():
    action = demo.sample_action()
    action["q_r_chunk"][1][0] = 9.0

    assert action["q_l_chunk"][1][0] != 9.0
