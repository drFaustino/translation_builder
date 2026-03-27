def classFactory(iface):
    from .translation_builder import TranslationBuilder
    return TranslationBuilder(iface)
