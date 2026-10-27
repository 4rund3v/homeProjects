// Package tllab proves, in code, the claims made in the mTLS lab
// (../mtls-and-cert-generation.md). No external files, no network: everything is
// generated in memory and verified. Run from this directory:
//
//     go test -v
//
// Each test is a claim from the lab, flipped into an assertion:
//
//   TestChainVerifies            — a leaf signed by the right CA passes x509.Verify
//   TestRogueCAFails            — a leaf signed by a DIFFERENT CA fails (the "rogue CA" drill)
//   TestWrongNameFails          — a valid chain to the wrong host fails SAN matching
//   TestMtlsAcceptsGoodClient   — server verifies a client cert signed by the client CA
//   TestMtlsRejectsRogueClient  — the same server rejects a client cert from a foreign CA
//
// These are the exact failure modes Part 2 of the lab walks you through by hand with
// openssl; here they're machine-checked so you can see the PASS/FAIL without a PKI.
package tllab

import (
	"crypto/ecdsa"
	"crypto/elliptic"
	"crypto/rand"
	"crypto/tls"
	"crypto/x509"
	"crypto/x509/pkix"
	"encoding/pem"
	"fmt"
	"math/big"
	"net"
	"testing"
	"time"
)

// certSpec is the minimal input to build a self- or CA-signed certificate.
type certSpec struct {
	commonName   string
	dnsNames     []string
	ca          bool
	pathLen     int
	keyUsage    x509.KeyUsage
	extKeyUsage []x509.ExtKeyUsage
}

// makeKey returns a fresh P-256 key — the modern default for both CAs and leaves.
func makeKey(t *testing.T) *ecdsa.PrivateKey {
	t.Helper()
	k, err := ecdsa.GenerateKey(elliptic.P256(), rand.Reader)
	if err != nil {
		t.Fatalf("generate key: %v", err)
	}
	return k
}

// signCert builds a certificate. If parent == nil it is self-signed (a root).
func signCert(t *testing.T, key *ecdsa.PrivateKey, spec certSpec, parent *x509.Certificate, parentKey *ecdsa.PrivateKey) *x509.Certificate {
	t.Helper()
	serial, _ := rand.Int(rand.Reader, new(big.Int).Lsh(big.NewInt(1), 63))
	serial = serial.Int64()

	template := x509.Certificate{
		SerialNumber: big.NewInt(serial),
		Subject:      pkix.Name{CommonName: spec.commonName, Organization: []string{"go-lab"}},
		NotBefore:    time.Now().Add(-time.Hour), // small backdate: clock-skew safety
		NotAfter:     time.Now().AddDate(1, 0, 0),
		KeyUsage:     spec.keyUsage,
		ExtKeyUsage:  spec.extKeyUsage,
		DNSNames:     spec.dnsNames,
	}
	if spec.ca {
		template.IsCA = true
		template.BasicConstraintsValid = true
		template.MaxPathLen = spec.pathLen
	}

	// A root signs itself; a leaf/intermediate is signed by its parent.
	subject, issuer, pub, priv := key, parentKey, &key.PublicKey, key
	if parent != nil {
		issuer, priv = parentKey, key // leaf: issuer = parent
		pub = &key.PublicKey
		_ = subject
	}

	der, err := x509.CreateCertificate(rand.Reader, &template, issuer, pub, priv)
	if err != nil {
		t.Fatalf("create cert: %v", err)
	}
	cert, err := x509.ParseCertificate(der)
	if err != nil {
		t.Fatalf("parse cert: %v", err)
	}
	return cert
}

// buildPKI constructs a root CA and a server leaf it signs. Returns the server cert,
// the server key, the root cert, and the root key (so other certs can be signed by it).
func buildPKI(t *testing.T) (server *x509.Certificate, serverKey *ecdsa.PrivateKey, root *x509.Certificate, rootKey *ecdsa.PrivateKey) {
	t.Helper()
	rootKey = makeKey(t)
	root = signCert(t, rootKey, certSpec{
		commonName: "go-lab-root",
		ca:         true,
		pathLen:    1,
		keyUsage:   x509.KeyUsageCertSign | x509.KeyUsageCRLSign,
	}, nil, rootKey)

	serverKey = makeKey(t)
	server = signCert(t, serverKey, certSpec{
		commonName:  "api.expense.local",
		dnsNames:    []string{"api.expense.local"},
		keyUsage:    x509.KeyUsageDigitalSignature | x509.KeyUsageKeyEncipherment,
		extKeyUsage: []x509.ExtKeyUsage{x509.ExtKeyUsageServerAuth},
	}, root, rootKey)
	return
}

// TestChainVerifies is the Go equivalent of `openssl verify -CAfile root leaf` → OK.
func TestChainVerifies(t *testing.T) {
	server, serverKey, root, _ := buildPKI(t)

	roots := x509.NewCertPool()
	roots.AddCert(root)
	_, err := server.Verify(x509.VerifyOptions{Roots: roots, DNSName: "api.expense.local"})
	if err != nil {
		t.Fatalf("expected the valid chain to verify, got: %v", err)
	}
}

// TestRogueCAFails reproduces the lab's Part-2 "a client cert the server's CA didn't
// sign → handshake fails" drill, in pure x509.Verify terms.
func TestRogueCAFails(t *testing.T) {
	// The honest CA the client will be handed.
	_, _, root, _ := buildPKI(t)

	// A completely separate, untrusted CA that also signs a "server" cert.
	rogueKey := makeKey(t)
	rogue := signCert(t, rogueKey, certSpec{
		commonName: "rogue-ca",
		ca:         true,
		keyUsage:   x509.KeyUsageCertSign,
	}, nil, rogueKey)

	rogueLeafKey := makeKey(t)
	rogueLeaf := signCert(t, rogueLeafKey, certSpec{
		commonName: "api.expense.local", // same host, different CA
		dnsNames:   []string{"api.expense.local"},
		keyUsage:   x509.KeyUsageDigitalSignature,
		extKeyUsage: []x509.ExtKeyUsage{x509.ExtKeyUsageServerAuth},
	}, rogue, rogueKey)

	// Verify the rogue leaf against the HONEST root pool.
	roots := x509.NewCertPool()
	roots.AddCert(root)
	_, err := rogueLeaf.Verify(x509.VerifyOptions{Roots: roots, DNSName: "api.expense.local"})
	if err == nil {
		t.Fatal("a rogue-CA leaf must NOT verify against the honest root pool")
	}
	// It SHOULD verify against its own (rogue) pool — that's the whole point of the
	// drill: the host checks out, the trust anchor is what's wrong.
	rogueRoots := x509.NewCertPool()
	rogueRoots.AddCert(rogue)
	if _, err := rogueLeaf.Verify(x509.VerifyOptions{Roots: rogueRoots, DNSName: "api.expense.local"}); err != nil {
		t.Fatalf("the rogue leaf should verify against its own rogue CA, got: %v", err)
	}
}

// TestWrongNameFails proves SAN matching is enforced: a valid chain to a different
// host fails, exactly like the lab's `openssl s_client -verify_hostname wrong`.
func TestWrongNameFails(t *testing.T) {
	server, _, root, _ := buildPKI(t)
	roots := x509.NewCertPool()
	roots.AddCert(root)
	_, err := server.Verify(x509.VerifyOptions{Roots: roots, DNSName: "wrong.example.com"})
	if err == nil {
		t.Fatal("verification against the wrong hostname must fail")
	}
}

// startMTLSServer stands up a real TLS server that REQUIRES and verifies client
// certificates, returning its address. It's the in-code version of
// `openssl s_server -Verify 1 -CAfile client-root`.
func startMTLSServer(t *testing.T, clientRoots *x509.CertPool, serverCert tls.Certificate, serverKey *ecdsa.PrivateKey) string {
	t.Helper()
	ln, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatalf("listen: %v", err)
	}
	cfg := &tls.Config{
		Certificates: []tls.Certificate{serverCert},
		ClientAuth:   tls.RequireAndVerifyClientCert,
		ClientCAs:    clientRoots,
		MinVersion:   tls.VersionTLS13,
	}
	srv := tls.NewListener(ln, cfg)
	go func() {
		for {
			conn, err := srv.Accept()
			if err != nil {
				return
			}
			// Handshake happens on Accept; drain and close.
			buf := make([]byte, 1)
			_, _ = conn.Read(buf)
			_ = conn.Close()
		}
	}()
	return ln.Addr().String()
}

func keyPairToTLS(t *testing.T, cert *x509.Certificate, key *ecdsa.PrivateKey, intermediates ...*x509.Certificate) tls.Certificate {
	t.Helper()
	der, err := cert.Raw // already DER
	_ = der
	blk := &pem.Block{Type: "CERTIFICATE", Bytes: cert.Raw}
	certPEM, _ := pem.EncodeToMemory(blk)
	keyDER, err := x509.MarshalECPrivateKey(key)
	if err != nil {
		t.Fatalf("marshal key: %v", err)
	}
	keyPEM, _ := pem.EncodeToMemory(&pem.Block{Type: "EC PRIVATE KEY", Bytes: keyDER})
	var full []byte
	full = append(full, certPEM...)
	for _, in := range intermediates {
		full = append(full, pem.EncodeToMemory(&pem.Block{Type: "CERTIFICATE", Bytes: in.Raw})...)
	}
	loaded, err := tls.X509KeyPair(full, keyPEM)
	if err != nil {
		t.Fatalf("X509KeyPair: %v", err)
	}
	return loaded
}

// TestMtlsAcceptsGoodClient + TestMtlsRejectsRogueClient prove, with a real
// handshake, that `RequireAndVerifyClientCert` enforces the client CA exactly as the
// lab's Part 2 does by hand.
func TestMtlsAcceptsGoodClient(t *testing.T) {
	server, serverKey, root, rootKey := buildPKI(t)
	clientRoots := x509.NewCertPool()
	clientRoots.AddCert(root)

	// The client presents a cert signed by the SAME CA the server trusts.
	clientKey := makeKey(t)
	clientCert := signCert(t, clientKey, certSpec{
		commonName:  "expense-client",
		keyUsage:    x509.KeyUsageDigitalSignature,
		extKeyUsage: []x509.ExtKeyUsage{x509.ExtKeyUsageClientAuth},
	}, root, rootKey) // signed by the server root, so it matches ClientCAs

	srvCert := keyPairToTLS(t, server, serverKey)
	addr := startMTLSServer(t, clientRoots, srvCert, serverKey)

	cfg := &tls.Config{
		Certificates: []tls.Certificate{keyPairToTLS(t, clientCert, clientKey)},
		RootCAs:      clientRoots,
		ServerName:   "api.expense.local",
		MinVersion:   tls.VersionTLS13,
	}
	conn, err := tls.Dial("tcp", addr, cfg)
	if err != nil {
		t.Fatalf("mTLS dial should succeed with a good client cert: %v", err)
	}
	defer conn.Close()
}

// TestMtlsRejectsRogueClient is the security claim: a client cert signed by a CA the
// server does NOT trust must fail the handshake, not just be logged.
func TestMtlsRejectsRogueClient(t *testing.T) {
	server, serverKey, root, _ := buildPKI(t)
	clientRoots := x509.NewCertPool()
	clientRoots.AddCert(root) // server trusts ONLY the honest root

	// A client cert from a DIFFERENT CA.
	rogueKey := makeKey(t)
	rogue := signCert(t, rogueKey, certSpec{commonName: "rogue-client-ca", ca: true, keyUsage: x509.KeyUsageCertSign}, nil, rogueKey)
	rogueClientKey := makeKey(t)
	rogueClient := signCert(t, rogueClientKey, certSpec{
		commonName:  "rogue-client",
		keyUsage:    x509.KeyUsageDigitalSignature,
		extKeyUsage: []x509.ExtKeyUsage{x509.ExtKeyUsageClientAuth},
	}, rogue, rogueKey)

	srvCert := keyPairToTLS(t, server, serverKey)
	addr := startMTLSServer(t, clientRoots, srvCert, serverKey)

	cfg := &tls.Config{
		Certificates: []tls.Certificate{keyPairToTLS(t, rogueClient, rogueClientKey)},
		RootCAs:      clientRoots,
		ServerName:   "api.expense.local",
		MinVersion:   tls.VersionTLS13,
	}
	if _, err := tls.Dial("tcp", addr, cfg); err == nil {
		t.Fatal("a client cert from an untrusted CA MUST fail the mTLS handshake")
	} else {
		// Expected: a certificate-verification error from the server side.
		t.Log("handshake correctly rejected:", err)
	}
}
