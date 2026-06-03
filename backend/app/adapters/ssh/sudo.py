def prepare_sudo_command(command: str, ssh_password: str | None) -> tuple[str, str | None]:
    if not ssh_password or "sudo" not in command:
        return command, None
    return (
        "\n".join(
            [
                "IFS= read -r NEXUSOPS_SUDO_PASSWORD",
                "export NEXUSOPS_SUDO_PASSWORD",
                "NEXUSOPS_ASKPASS=$(mktemp)",
                "trap 'rm -f \"$NEXUSOPS_ASKPASS\"' EXIT",
                "cat >\"$NEXUSOPS_ASKPASS\" <<'NEXUSOPS_ASKPASS_EOF'",
                "#!/bin/sh",
                "printf '%s\\n' \"$NEXUSOPS_SUDO_PASSWORD\"",
                "NEXUSOPS_ASKPASS_EOF",
                "chmod 700 \"$NEXUSOPS_ASKPASS\"",
                "sudo() { SUDO_ASKPASS=\"$NEXUSOPS_ASKPASS\" command sudo -A -p '' \"$@\"; }",
                command,
            ]
        ),
        f"{ssh_password}\n",
    )
