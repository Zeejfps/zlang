namespace LexerModule.Tests;

[TestFixture]
public class KeywordTests
{
    [Test]
    public void TestFuncKeyword()
    {
        const string input = "func";
        var tokens = Lexer.Tokenize(input);
        
        Assert.That(tokens, Is.EquivalentTo(new[]
        {
            new Token(TokenKind.KeywordFunc, "func", 1, 1),
            new Token(TokenKind.EOF, string.Empty, 1, 5)
        }));
    }
    
    [Test]
    public void TestDeferKeyword()
    {
        const string input = "defer";
        var tokens = Lexer.Tokenize(input);
        
        Assert.That(tokens, Is.EquivalentTo(new[]
        {
            new Token(TokenKind.KeywordDefer, "defer", 1, 1),
            new Token(TokenKind.EOF, string.Empty, 1, 6)
        }));
    }
}