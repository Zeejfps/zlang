namespace LexerModule.Tests;

[TestFixture]
public class Tests
{

    [Test]
    public void Test1()
    {
        var tokens = Lexer
            .Tokenize("module string = std.string");

        Assert.That(tokens, Is.EquivalentTo(new[]
        {
            new Token(TokenKind.ModuleKeyWord, "module", 1, 1),
            new Token(TokenKind.Identifier, "string", 1, 8),
            new Token(TokenKind.Equals, "=", 1, 15),
            new Token(TokenKind.Identifier, "std", 1, 17),
            new Token(TokenKind.Dot, ".", 1, 20),
            new Token(TokenKind.Identifier, "string", 1, 21),
            new Token(TokenKind.Eof, string.Empty, 1, 27)
        }));
    }
}