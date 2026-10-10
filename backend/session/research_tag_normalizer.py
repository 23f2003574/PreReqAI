def normalize_research_tag_name(

    name: str,

) -> str:

    value = (

        name
        .strip()
        .lstrip("#")
        .strip()
        .casefold()
    )

    value = "-".join(
        value.split()
    )

    normalized = "".join(

        character

        for character

        in value

        if (

            character.isalnum()

            or character in {
                "-",
                "_",
            }
        )
    )

    if not normalized:

        raise ValueError(

            "Research tag name "
            "cannot be empty"
        )

    return normalized
