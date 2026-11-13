# Guía del revisor — `rxre-engine` en ≈15 minutos

Objetivo: reproducir (o refutar) la cadena de evidencia publicada, sin confiar en
la palabra del autor. Si algo no reproduce, **documéntalo: es el resultado que
más importa**.

## 0. Anota tu entorno (pegar antes de empezar)

```sh
uname -a
cat /etc/os-release 2>/dev/null | head -3
gcc --version | head -1
python3 --version
gcc -v 2>&1 | tail -1
sha256sum /usr/bin/ls /usr/bin/wc
locale -a 2>/dev/null | grep -E '^(C)\.?$|es_AR\.utf8|C\.UTF-8' | head
```

Referencia sellada (si difiere, la cadena con oráculo nativo no aplica):
`/usr/bin/ls` = `54e936d37decdad9ecaf189b1de347605a0a99037ec87bd17679b6cbde871a0c`
`/usr/bin/wc` = `81d614595c717be908fce809713702efd35ce5a56f5ab7cbc497d1a61eb1a38f`

## 1. Clon y commit

```sh
git clone https://github.com/LexLuthorPrimero/rxre-engine
cd rxre-engine
git log --oneline -1     # anota el commit exacto
```

## 2. Integridad del paquete

```sh
sha256sum -c evidence/r3/SHA256SUMS   # si existe en esta versión; si no, verify.sh lo hace
sh evidence/r3/verify.sh
```

`verify.sh` ejecuta, en orden fail-closed: (1) manifiesto sellado (42 artefactos),
(2) identidad nativa de `ls`/`wc`, (3–4) build + diferencial de las dos
generaciones (34.145×2), (5) challenge corpus (3.100 + 3.241), (6) invariancia
de locale, (7) i18n black-box, (8–10) wc en `LC_ALL=C` y `es_AR.utf8` (11 corpora),
(11) suite pytest (49 passed, 2 skipped en clon público), (12) resumen.
Cola esperada: `VERIFY: all steps passed`.

## 3. Qué comprobar tú mismo (no te lo crea nadie, ni el autor)

- Que los hashes del oráculo real coinciden antes de cualquier salto (el script
  aborta si no: observa ese comportamiento abortando a propósito, p. ej. con un
  binario interpuesto en `PATH` o un `ls` distinto).
- Que la suite pytest no reporta fallos (puede reportar 2 *skips* honestos).
- Que `evidence/r3/verify.sh` no ejecuta nada de red ni de hardware.

## 4. Prueba de fuego: tu propio corpus adversarial

```sh
python3 evidence/r3/challenge_cr_20261126/gen_challenge_cr.py   # lee su semilla; no lo edites aún
# o genera el tuyo: nombres UTF-8 largos, números con ceros, '.' interior,
# grupos de dígitos, ~, leadbytes 0x80+, concatenaciones a==b, etc.
```

Luego compáralo contra `ls -v` nativo (con binario de **tu** sistema) y contra la
reconstrucción (`evidence/r3/reconstruction/filenvercmp.c`, ya sellada). Si tu
corpus produce un mismatch: primero minimiza, después abre un issue con
`CONTRAEJEMPLO.md`. Un contraejemplo válido invalida el hito entero. Es el punto.

## 5. Qué NO significa PASS

`VERIFY: all steps passed` significa exactamente eso: la cadena sellada reprodujo
los resultados en tu entorno. No significa: que el motor reconstruya binarios en
general, que esté verificado por terceros (eso eres tú decidiendo), ni que haya
garantía más allá del dominio sellado.

## 6. Al terminar

Rellena y archiva:
- commit exacto del clon,
- commit exacto del release consultado (si usaste el zip: anota su SHA-256),
- salida completa de `verify.sh`,
- tu dictamen: `REPRODUCE / NO REPRODUCE / PARCIAL (explica)`.

Si eliges `NO REPRODUCE` con evidencia, habrás aportado más al proyecto que cien
pruebas amables.
