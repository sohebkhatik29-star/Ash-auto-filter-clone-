# 🎯 TOKEN VERIFICATION SETTINGS MODULE
# Loader: fetch base from known-good commit, inject clone-client admin check for VERIFY LOG CHANNEL
import urllib.request

_BASE_URL = (
    "https://raw.githubusercontent.com/sohebkhatik29-star/Ash-auto-filter-clone-/"
    "35837d9c01a7de6829596db93bb32a920afbc841/settings_modules/token_verify.py"
)

def _load():
    with urllib.request.urlopen(_BASE_URL, timeout=30) as resp:
        src = resp.read().decode("utf-8")

    # Find and replace the admin-check block so clone settings use clone client
    needle = 't_msg = await client.send_message(ch_id, "✅ <b>Verify log channel connected successfully!</b>")'
    if needle not in src:
        # already patched or different structure
        pass
    else:
        idx = src.find('t_msg = await client.send_message(ch_id')
        if idx > 0:
            line_start = src.rfind("\n", 0, idx) + 1
            try_line = src.rfind("\n            try:", 0, idx)
            if try_line < 0:
                try_line = src.rfind("try:", 0, idx)
                try_line = src.rfind("\n", 0, try_line) + 1 if try_line > 0 else line_start
            else:
                try_line = try_line + 1  # after newline

            inject = (
                "            # Clone log channel: test with clone client when target_bid set\n"
                "            test_client = client\n"
                "            if target_bid:\n"
                "                try:\n"
                "                    from plugins.clone import get_clone_client\n"
                "                    clone_cli = get_clone_client(target_bid)\n"
                "                    if clone_cli is not None:\n"
                "                        test_client = clone_cli\n"
                "                    else:\n"
                "                        try:\n"
                "                            await prompt_msg.delete()\n"
                "                        except Exception:\n"
                "                            pass\n"
                "                        await client.send_message(\n"
                "                            user_id,\n"
                '                            "❌ <b>Clone bot is not running right now.</b>\\n"\n'
                '                            "Activate/restart the clone first, then set the log channel again."\n'
                "                        )\n"
                "                        clear_user_session(user_id)\n"
                "                        return\n"
                "                except Exception as e:\n"
                "                    try:\n"
                "                        await prompt_msg.delete()\n"
                "                    except Exception:\n"
                "                        pass\n"
                '                    await client.send_message(user_id, f"❌ <b>Could not get clone client:</b> {e}")\n'
                "                    clear_user_session(user_id)\n"
                "                    return\n"
            )
            src = src[:try_line] + inject + src[try_line:]
            src = src.replace(
                "t_msg = await client.send_message(ch_id, \"✅ <b>Verify log channel connected successfully!</b>\")",
                "t_msg = await test_client.send_message(ch_id, \"✅ <b>Verify log channel connected successfully!</b>\")",
                1,
            )
            src = src.replace(
                'await client.send_message(user_id, f"❌ <b>Bot is not admin in channel! Error:</b> {e}")',
                'who = "Clone bot" if target_bid else "Bot"\n'
                '                await client.send_message(user_id, f"❌ <b>{who} is not admin in channel! Error:</b> {e}")',
                1,
            )

    src = src.replace(
        "Make sure this bot is an ADMIN in the channel! Send /cancel to abort.",
        "Make sure the clone bot (when setting for a clone) is an ADMIN in the channel! Send /cancel to abort.",
        1,
    )

    g = {"__name__": __name__, "__file__": __file__}
    exec(compile(src, __file__, "exec"), g, g)
    for k, v in list(g.items()):
        if not k.startswith("_"):
            globals()[k] = v

_load()
