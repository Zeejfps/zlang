namespace LexerModule.Tests;

[TestFixture]
public class SymbolsTests
{
    [Test]
    public void TestCurlyBraces()
    {
        const string input = "{}";
        var tokens = Lexer.Tokenize(input);
        
        Assert.That(tokens, Is.EquivalentTo(new[]
        {
            new Token(TokenKind.SymbolLeftCurlyBrace, "{", 1, 1),
            new Token(TokenKind.SymbolRightCurlyBrace, "}", 1, 2),
            new Token(TokenKind.EOF, string.Empty, 1, 3)
        }));
    }
    
    [Test]
    public void TestSquareBrackets()
    {
        const string input = "[]";
        var tokens = Lexer.Tokenize(input);
        
        Assert.That(tokens, Is.EquivalentTo(new[]
        {
            new Token(TokenKind.SymbolLeftSquareBracket, "[", 1, 1),
            new Token(TokenKind.SymbolRightSquareBracket, "]", 1, 2),
            new Token(TokenKind.EOF, string.Empty, 1, 3)
        }));
    }
    
    [Test]
    public void TestReturnArrow()
    {
        const string input = "->";
        var tokens = Lexer.Tokenize(input);
        
        Assert.That(tokens, Is.EquivalentTo(new[]
        {
            new Token(TokenKind.SymbolReturnArrow, "->", 1, 1),
            new Token(TokenKind.EOF, string.Empty, 1, 3)
        }));
    }
    
    [Test]
    public void TestPlusEqualsArrow()
    {
        const string input = "+=";
        var tokens = Lexer.Tokenize(input);
        
        Assert.That(tokens, Is.EquivalentTo(new[]
        {
            new Token(TokenKind.SymbolPlusEquals, "+=", 1, 1),
            new Token(TokenKind.EOF, string.Empty, 1, 3)
        }));
    }
    
    [Test]
    public void TestStarArrow()
    {
        const string input = "*";
        var tokens = Lexer.Tokenize(input);
        
        Assert.That(tokens, Is.EquivalentTo(new[]
        {
            new Token(TokenKind.SymbolStar, "*", 1, 1),
            new Token(TokenKind.EOF, string.Empty, 1, 2)
        }));
    }
    
    [Test]
    public void TestPlus()
    {
        const string input = "+";
        var tokens = Lexer.Tokenize(input);
        
        Assert.That(tokens, Is.EquivalentTo(new[]
        {
            new Token(TokenKind.SymbolPlus, "+", 1, 1),
            new Token(TokenKind.EOF, string.Empty, 1, 2)
        }));
    }
    
    [Test]
    public void TestPlusBeforePlusEquals()
    {
        const string input = "++=";
        var tokens = Lexer.Tokenize(input);
        
        Assert.That(tokens, Is.EquivalentTo(new[]
        {
            new Token(TokenKind.SymbolPlus, "+", 1, 1),
            new Token(TokenKind.SymbolPlusEquals, "+=", 1, 2),
            new Token(TokenKind.EOF, string.Empty, 1, 4)
        }));
    }
    
    [Test]
    public void TestEqualsEquals()
    {
        const string input = "==";
        var tokens = Lexer.Tokenize(input);
        
        Assert.That(tokens, Is.EquivalentTo(new[]
        {
            new Token(TokenKind.SymbolEqualsEquals, "==", 1, 1),
            new Token(TokenKind.EOF, string.Empty, 1, 3)
        }));
    }
    
    [Test]
    public void TestNotEqualsEquals()
    {
        const string input = "!=";
        var tokens = Lexer.Tokenize(input);
        
        Assert.That(tokens, Is.EquivalentTo(new[]
        {
            new Token(TokenKind.SymbolNotEquals, "!=", 1, 1),
            new Token(TokenKind.EOF, string.Empty, 1, 3)
        }));
    }
}