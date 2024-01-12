from strictyaml import CommaSeparated, Int, Map, MapCombined, Optional, Regex, Seq, Str

RESTAURANT_SCHEMA = Map(
    {
        "author": Str(),
        "restaurant": Map(
            {
                "name": Str(),
                "street_address": Str(),
                "city": Str(),
                "country_code": Regex("[A-Z]{2}"),
                "tags": CommaSeparated(Str()),
                Optional("homepage_url"): Str(),
                Optional("googlemaps_url"): Str(),
                Optional("facebook_url"): Str(),
                Optional("instagram_url"): Str(),
                Optional("online_menu_url"): Str(),
                Optional("yelp_url"): Str(),
                Optional("tripadvisor_url"): Str(),
            }
        ),
        Optional("menu"): Map(
            {
                "language_codes": Seq(Str()),
                "pages": Seq(
                    Map(
                        {
                            Optional("page_image_url"): Str(),
                            Optional("page_url"): Str(),
                            Optional("sections"): Seq(
                                # MapCombined combines Map (item 1) and MapPattern (items 2-3)
                                # https://hitchdev.com/strictyaml/using/alpha/compound/map-combined/
                                MapCombined(
                                    {
                                        Optional("name_zh-Hans"): Str(),
                                        Optional("name_en"): Str(),
                                        Optional("menu_items"): Seq(
                                            MapCombined(
                                                {
                                                    Optional("item_number"): Str(),
                                                    Optional("name_zh-Hans"): Str(),
                                                    Optional("name_en"): Str(),
                                                    Optional(
                                                        "description_zh-Hans"
                                                    ): Str(),
                                                    Optional("image_url"): Str(),
                                                    Optional("price"): Str(),
                                                    Optional("spice_heat_level"): Int(),
                                                },
                                                Str(),  # validator for keys (both defined and undefined)
                                                Str(),  # validator for values of undefined keys
                                            )
                                        ),
                                    },
                                    Str(),  # validator for keys (both defined and undefined)
                                    Str(),  # validator for values of undefined keys
                                )
                            ),
                            Optional("page_footer"): Str(),
                        }
                    )
                ),
            }
        ),
    }
)
