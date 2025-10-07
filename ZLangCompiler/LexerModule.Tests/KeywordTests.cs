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
    
    [Test]
    public void TestUnionKeyword()
    {
        const string input = "union";
        var tokens = Lexer.Tokenize(input);
        
        Assert.That(tokens, Is.EquivalentTo(new[]
        {
            new Token(TokenKind.KeywordUnion, "union", 1, 1),
            new Token(TokenKind.EOF, string.Empty, 1, 6)
        }));
    }
    
    [Test]
    public void TestOperatorKeyword()
    {
        const string input = "operator";
        var tokens = Lexer.Tokenize(input);
        
        Assert.That(tokens, Is.EquivalentTo(new[]
        {
            new Token(TokenKind.KeywordOperator, "operator", 1, 1),
            new Token(TokenKind.EOF, string.Empty, 1, 9)
        }));
    }
    
    [Test]
    public void TestReturnKeyword()
    {
        const string input = "return";
        var tokens = Lexer.Tokenize(input);
        
        Assert.That(tokens, Is.EquivalentTo(new[]
        {
            new Token(TokenKind.KeywordReturn, "return", 1, 1),
            new Token(TokenKind.EOF, string.Empty, 1, 7)
        }));
    }
}