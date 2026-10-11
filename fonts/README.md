# Fuentes bundleadas (SIL Open Font License 1.1)

Se registran al arrancar con `styles.register_fonts()` (QFontDatabase). Licencias: `OFL-*.txt`.

| Familia | Origen | Versión | Archivos |
|---|---|---|---|
| Public Sans | https://github.com/uswds/public-sans (release oficial) | v2.001 | Regular, Medium, SemiBold, Bold |
| JetBrains Mono | https://github.com/JetBrains/JetBrainsMono (release oficial) | v2.304 | Regular, Medium, SemiBold, Bold |
| Fraunces | https://github.com/undercasetype/Fraunces (release oficial) | 1.000 | Medium, SemiBold |

Fraunces solo trae release variable (+ estáticos con eje opsz fijo y nombres propios): los dos pesos
se instanciaron del TTF variable oficial con `fontTools.varLib.instancer`
(SOFT=0, WONK=0, opsz=72, wght=500/600) y se renombraron a la familia «Fraunces» (nameID 1/2/4/6/16/17).
fontTools es herramienta de desarrollo, no dependencia de runtime.

## SHA256

```
a795f0ff6d1fd89aaa4c9a81675b1a9740aee71c8f553be9949ac9702384f341  Fraunces-Medium.ttf
97b2c7a023442b79c1b5b93bb30b617fbc7d63544b24ff8abc7dd6072632651d  Fraunces-SemiBold.ttf
5590990c82e097397517f275f430af4546e1c45cff408bde4255dad142479dcb  JetBrainsMono-Bold.ttf
31c92d01a8a08528b718a43addf0ad3df0af2ca4b7b3290a452f70f358e14d3d  JetBrainsMono-Medium.ttf
a0bf60ef0f83c5ed4d7a75d45838548b1f6873372dfac88f71804491898d138f  JetBrainsMono-Regular.ttf
1b3bfa1ed5665a4ce3f9feb68d2d4e40e70bf8b4b7d9a3edd418f321b4e166a0  JetBrainsMono-SemiBold.ttf
bddd96a0bcd49b292524b4beff57d770ce97482fb3f84b788959422e06b863a6  PublicSans-Bold.ttf
ca804b5c7569a59f1507c5d3e1aa389c354bf2ae6b864bc537fa7672d28469d6  PublicSans-Medium.ttf
b577e9bc9887284e90aae5ad0699689ce36b5cd96207efbec68f77f8aed88379  PublicSans-Regular.ttf
9f537d607dc78450841dc31c401e3c4ba7a0ba7217e8b34c1be684a983806399  PublicSans-SemiBold.ttf
```
