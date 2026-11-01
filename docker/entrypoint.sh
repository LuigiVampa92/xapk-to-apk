#!/bin/bash
set -e

PROPERTIES_FILE="xapktoapk.sign.properties"
KEYSTORE_FILE="xapktoapk.keystore"

if [ ! -f "$PROPERTIES_FILE" ]; then
	if [ ! -f "$KEYSTORE_FILE" ]; then
		echo "[*] No signing configuration found, generating a keystore with a randomly generated key."
		PASSWORD="$(LC_ALL=C tr -dc '[:alnum:]' < /dev/urandom | head -c20)"
		echo "[*] Generated keystore password: $PASSWORD (save it if you want to reuse the same signature in future runs)"
		keytool \
			-genkey \
			-v \
			-keystore "$KEYSTORE_FILE" \
			-alias xapktoapk \
			-keyalg RSA \
			-keysize 2048 \
			-validity 10000 \
			-storepass "$PASSWORD" \
			-keypass "$PASSWORD" \
			-dname "CN=xapktoapk, OU=xapktoapk, O=xapktoapk, L=xapktoapk, S=xapktoapk, C=US"
		cat <<EOF > "$PROPERTIES_FILE"
sign.enabled=true
sign.keystore.file=/xapktoapk/$KEYSTORE_FILE
sign.keystore.password=$PASSWORD
sign.key.alias=xapktoapk
sign.key.password=$PASSWORD
sign.v1.enabled=true
sign.v2.enabled=true
sign.v3.enabled=true
EOF
	else
		echo "[!] Keystore $KEYSTORE_FILE exists but $PROPERTIES_FILE is missing." >&2
		echo "    Not regenerating the keystore because that would change the signature." >&2
		echo "    Mount your own $PROPERTIES_FILE (with sign.keystore.file pointing to the keystore) or delete the keystore." >&2
		exit 1
	fi
fi

exec python xapktoapk.py "$@"
